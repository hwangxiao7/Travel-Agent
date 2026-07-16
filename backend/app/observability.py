from __future__ import annotations

import itertools
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

# Background JSON logs — not printed to the terminal.
_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"  # backend/logs/
_LOG_FILE = _LOG_DIR / "travel_agent.log"

# High-frequency, low-signal endpoints whose successful responses flood the log
# (health polls, per-launch /auth/me bursts, Prometheus scrapes). We keep only
# 1-in-N of their 2xx/3xx lines; anything >=400 is always logged in full.
_NOISY_PATHS = frozenset({"/api/health", "/api/auth/me", "/metrics"})
_noisy_counters: dict[str, "itertools.count[int]"] = defaultdict(lambda: itertools.count())


def _should_log_request(path: str, status: int) -> bool:
    """Always log errors; down-sample noisy successful paths by log_sample_noisy."""
    if status >= 400:
        return True
    if path not in _NOISY_PATHS:
        return True
    every = settings.log_sample_noisy or 1
    if every <= 1:
        return True
    # Log the 1st, then every Nth (counter starts at 0).
    return next(_noisy_counters[path]) % every == 0

# Request-scoped ids (also attached to every JSON log line).
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")

SERVICE_NAME = "spontaneous-travel-agent"

request_count = Counter(
    "request_count",
    "Total HTTP requests",
    ["method", "path", "status"],
)
request_latency_ms = Histogram(
    "request_latency_ms",
    "HTTP request latency in milliseconds",
    ["method", "path"],
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000),
)
llm_latency_ms = Histogram(
    "llm_latency_ms",
    "LLM generation latency in milliseconds",
    buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000),
)
rag_latency_ms = Histogram(
    "rag_latency_ms",
    "RAG retrieval / embedding latency in milliseconds",
    ["operation"],
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 15000),
)
external_api_latency_ms = Histogram(
    "external_api_latency_ms",
    "External API call latency in milliseconds",
    ["api"],
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 15000, 30000),
)
cache_hit_count = Counter("cache_hit_count", "Embedding cache hits")
cache_miss_count = Counter("cache_miss_count", "Embedding cache misses")
external_api_failure_count = Counter(
    "external_api_failure_count",
    "External API failures",
    ["api"],
)

_tracer: trace.Tracer | None = None
_logger = logging.getLogger("travel_agent")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None) or trace_id_var.get() or None,
            "span_id": getattr(record, "span_id", None) or span_id_var.get() or None,
        }
        for key in ("span", "latency_ms", "path", "method", "status", "api", "error"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int | None = None) -> None:
    """Write structured JSON logs to a size-rotated file — nothing in the terminal.

    Level comes from LOG_LEVEL (default INFO); the file rotates at LOG_MAX_BYTES
    keeping LOG_BACKUP_COUNT older files so it can never grow unbounded.
    """
    if level is None:
        level = logging.getLevelName(str(settings.log_level).upper())
        if not isinstance(level, int):
            level = logging.INFO
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())
    file_handler.setLevel(level)

    # App observability logger: file only.
    _logger.handlers.clear()
    _logger.addHandler(file_handler)
    _logger.setLevel(level)
    _logger.propagate = False

    # Leave uvicorn's default console access/error logs alone (short, useful).
    # Do not attach our JSON formatter to the root logger.


def setup_tracing() -> trace.Tracer:
    """In-process tracer only — no console span dump."""
    global _tracer
    if _tracer is not None:
        return _tracer
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    # No ConsoleSpanExporter: spans feed metrics/attributes in-process only.
    # Wire an OTLP exporter here later if you want a remote collector.
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(SERVICE_NAME)
    return _tracer


def get_tracer() -> trace.Tracer:
    return _tracer or setup_tracing()


def current_trace_id() -> str:
    return trace_id_var.get()


def _set_span_ids(span: trace.Span) -> None:
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        span_id_var.set(format(ctx.span_id, "016x"))
        # Prefer OTel trace id when present; keep middleware-assigned id otherwise.
        if not trace_id_var.get():
            trace_id_var.set(format(ctx.trace_id, "032x"))


@contextmanager
def traced(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    latency_metric: Histogram | None = None,
    latency_labels: dict[str, str] | None = None,
) -> Iterator[trace.Span]:
    """Sync span helper that also logs latency as structured JSON."""
    tracer = get_tracer()
    start = time.perf_counter()
    prev_span = span_id_var.get()
    with tracer.start_as_current_span(name) as span:
        _set_span_ids(span)
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(k, v)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        finally:
            ms = (time.perf_counter() - start) * 1000
            span.set_attribute("latency_ms", round(ms, 2))
            if latency_metric is not None:
                if latency_labels:
                    latency_metric.labels(**latency_labels).observe(ms)
                else:
                    latency_metric.observe(ms)
            _logger.debug(
                "span completed",
                extra={"span": name, "latency_ms": round(ms, 2)},
            )
            span_id_var.set(prev_span)


@asynccontextmanager
async def atraced(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    latency_metric: Histogram | None = None,
    latency_labels: dict[str, str] | None = None,
) -> AsyncIterator[trace.Span]:
    """Async span helper that also logs latency as structured JSON."""
    with traced(
        name,
        attributes=attributes,
        latency_metric=latency_metric,
        latency_labels=latency_labels,
    ) as span:
        yield span


def record_external_failure(api: str, error: str = "failed") -> None:
    external_api_failure_count.labels(api=api).inc()
    # Truncate so a giant upstream body can't bloat a single log line.
    _logger.warning("external api failure", extra={"api": api, "error": str(error)[:500]})


def record_cache_hit(n: int = 1) -> None:
    if n > 0:
        cache_hit_count.inc(n)


def record_cache_miss(n: int = 1) -> None:
    if n > 0:
        cache_miss_count.inc(n)


def _metric_path(request: Request) -> str:
    """Templated route path (e.g. /api/places/{place_name}/reviews) for metric
    labels, so path params don't blow up Prometheus cardinality. Unmatched
    requests (404s / random scans) collapse to a single 'unmatched' bucket."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-trace-id") or request.headers.get("x-request-id")
        tid = incoming or uuid.uuid4().hex
        token = trace_id_var.set(tid)
        # Also stash on scope state: the contextvar doesn't reliably reach the
        # exception handler's task, but request.state (shared via scope) does.
        request.state.trace_id = tid
        path = request.url.path
        method = request.method
        start = time.perf_counter()
        status_code = 500
        try:
            async with atraced(
                f"{method} {path}",
                attributes={"http.method": method, "http.route": path, "trace_id": tid},
            ):
                response = await call_next(request)
                status_code = response.status_code
                response.headers["X-Trace-Id"] = tid
                return response
        finally:
            ms = (time.perf_counter() - start) * 1000
            # Templated path bounds metric label cardinality (see _metric_path).
            metric_path = _metric_path(request)
            request_count.labels(method=method, path=metric_path, status=str(status_code)).inc()
            request_latency_ms.labels(method=method, path=metric_path).observe(ms)
            if _should_log_request(path, status_code):
                _logger.info(
                    "request completed",
                    extra={
                        "method": method,
                        "path": path,
                        "status": status_code,
                        "latency_ms": round(ms, 2),
                        "trace_id": tid,
                    },
                )
            trace_id_var.reset(token)


async def _log_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for un-handled 500s: record the full stack in the JSON log,
    keyed by the request's trace_id, and echo that trace_id back to the client
    so a user-reported failure can be found in the log immediately.

    FastAPI's own handlers for HTTPException / RequestValidationError are more
    specific and still win, so this only fires on genuinely unexpected errors.
    """
    tid = getattr(request.state, "trace_id", None) or trace_id_var.get() or None
    _logger.error(
        "unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status": 500,
            "trace_id": tid,
        },
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error", "trace_id": tid},
        headers={"X-Trace-Id": tid} if tid else None,
    )


def setup_observability(app: FastAPI) -> None:
    setup_logging()
    setup_tracing()
    app.add_middleware(TracingMiddleware)
    app.add_exception_handler(Exception, _log_unhandled_exception)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
