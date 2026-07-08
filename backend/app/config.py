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
    openai_base_url: str = ""  # custom endpoint (e.g. Ark); blank = api.openai.com
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"  # RAG semantic retrieval
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"
    mapbox_token: str = ""
    openweather_api_key: str = ""
    ticketmaster_api_key: str = ""
    rapidapi_key: str = ""
    rapidapi_flights_host: str = "flights-sky.p.rapidapi.com"
    cors_origins: str = "http://localhost:5173"


settings = Settings()
