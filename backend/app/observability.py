from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Background JSON logs — not printed to the terminal.
_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"  # backend/logs/
_LOG_FILE = _LOG_DIR / "travel_agent.log"

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


def setup_logging(level: int = logging.INFO) -> None:
    """Write structured JSON logs to a file only — nothing shown in the terminal."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
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


def record_external_failure(api: str) -> None:
    external_api_failure_count.labels(api=api).inc()
    _logger.warning("external api failure", extra={"api": api, "error": "failed"})


def record_cache_hit(n: int = 1) -> None:
    if n > 0:
        cache_hit_count.inc(n)


def record_cache_miss(n: int = 1) -> None:
    if n > 0:
        cache_miss_count.inc(n)


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-trace-id") or request.headers.get("x-request-id")
        tid = incoming or uuid.uuid4().hex
        token = trace_id_var.set(tid)
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
            # Collapse path params for cardinality; keep exact for known API routes.
            metric_path = path if path.startswith("/api/") or path == "/metrics" else path
            request_count.labels(method=method, path=metric_path, status=str(status_code)).inc()
            request_latency_ms.labels(method=method, path=metric_path).observe(ms)
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


def setup_observability(app: FastAPI) -> None:
    setup_logging()
    setup_tracing()
    app.add_middleware(TracingMiddleware)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
