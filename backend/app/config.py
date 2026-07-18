from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root .env (this file is backend/app/config.py -> parents[2] == repo root)
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV), env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: str = "openai"  # openai | anthropic | template
    openai_api_key: str = ""
    openai_base_url: str = ""  # OpenAI-compatible gateway; blank = api.openai.com
    openai_model: str = "gpt-4o-mini"
    # Vision-only model for screenshot inspiration (blank → openai_model).
    # Used only when INSPIRATION_EXTRACT_MODE=vision or auto OCR fallback.
    openai_vision_model: str = ""
    # Screenshot inspiration extraction: ocr_text | vision | auto
    # ocr_text = local OCR + text LLM (cheap); vision = image→VL model; auto = OCR first.
    inspiration_extract_mode: str = "auto"
    inspiration_nomination_k: int = 3
    inspiration_geo_cell_deg: float = 0.5
    # Merge nominations into one canonical place when within this radius (miles).
    inspiration_merge_radius_miles: float = 0.35
    openai_embed_model: str = "text-embedding-3-small"  # RAG semantic retrieval
    # RAG embedding backend: "api" (OpenAI-compatible / Ollama) or "local" (PyTorch).
    embedding_backend: str = "api"
    local_embed_model: str = "BAAI/bge-small-en-v1.5"
    # Optional cross-encoder rerank after hybrid retrieval (needs sentence-transformers).
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 20  # hybrid top-N fed into the reranker
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"
    mapbox_token: str = ""
    openweather_api_key: str = ""
    ticketmaster_api_key: str = ""
    rapidapi_key: str = ""
    rapidapi_flights_host: str = "flights-sky.p.rapidapi.com"
    # TikTok travel-guide scraping (subscribe to the API on RapidAPI first).
    rapidapi_tiktok_host: str = "tiktok-scraper7.p.rapidapi.com"
    # Xiaohongshu / RED note scraping (subscribe to a RED scraper on RapidAPI).
    # Blank = disabled; reuses the same RAPIDAPI_KEY.
    rapidapi_xhs_host: str = ""
    # Instagram post scraping (subscribe to an IG scraper on RapidAPI).
    # Blank = disabled; reuses the same RAPIDAPI_KEY.
    rapidapi_instagram_host: str = ""
    # Reddit (AUTHORIZED source — official API). Create a "script"/"web" app at
    # https://www.reddit.com/prefs/apps and use application-only OAuth.
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "local-discovery/0.1 by u/yourname"
    # Compliance gate: RapidAPI TikTok/IG/RED scrapers are unauthorized third-party
    # scraping. OFF by default so App Store / production never depends on them.
    # Turn on ONLY for local dev experiments.
    enable_social_scraping: bool = False
    # Trending-spot ingestion: cross-validation + freshness knobs.
    trending_radius_miles: int = 40  # spots kept within this range of a destination
    trending_stale_days: int = 45  # spots not re-seen within N days drop off serving
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Account / JWT (change jwt_secret in production).
    jwt_secret: str = "dev-change-me-spontaneous-travel"
    jwt_expire_hours: int = 168  # 7 days
    database_url: str = ""  # blank → sqlite file under backend/data/
    # Observability / logging knobs.
    log_level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    log_max_bytes: int = 20_000_000  # rotate travel_agent.log at ~20 MB
    log_backup_count: int = 5  # keep N rotated files (.1 … .N)
    # Down-sample floods of successful, low-value requests (health, /auth/me):
    # keep 1 in N. Errors (>=400) are always logged. 1 = log everything.
    log_sample_noisy: int = 20
    # --- Feedback alerts (email on new user feedback) ---
    # SMTP is optional: when unset, feedback is still stored, just not emailed.
    # Gmail: host=smtp.gmail.com port=587 user=<you>@gmail.com pass=<app password>.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # blank → falls back to smtp_user
    feedback_alert_email: str = "hwangxiao7@gmail.com"  # where alerts go
    # Bearer-style token guarding the read-only feedback admin endpoint.
    admin_token: str = ""

    # China-market auth (default OFF — turn on when deploying domestically).
    auth_phone_enabled: bool = False
    auth_wechat_enabled: bool = False
    auth_phone_dev_code: str = ""  # optional fixed 6-digit OTP for local QA
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_redirect_uri: str = ""  # e.g. https://your.domain/api/auth/wechat/callback


settings = Settings()
