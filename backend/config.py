"""Application configuration.

Loads environment variables from the repo-root ``.env.local`` (falling back to
``.env``) and exposes a cached ``settings`` object. Anything secret (API keys,
database URLs) is read from the environment and never hard-coded here.

The ``mock_llm`` flag lets the whole agent pipeline run without any network or
OpenAI cost — useful for tests and local demos. When ``MOCK_LLM`` is not set
explicitly it defaults to *on* whenever no ``OPENAI_API_KEY`` is available, so
the app is always runnable out of the box.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Populate os.environ early so the LLM factory (which reads os.environ directly)
# and pydantic-settings below both see the same values. ``.env.local`` wins.
load_dotenv(_REPO_ROOT / ".env", override=False)
load_dotenv(_REPO_ROOT / ".env.local", override=True)


def _str_to_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    """Runtime configuration for the backend service."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # LLM
    openai_api_key: str = ""
    mock_llm: bool = False

    # Agent behaviour
    max_redesigns: int = 2  # cost>budget feedback-loop iterations before giving up

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    cors_origins: str = "http://localhost:3000"

    # Infra (unused for the mock flow but read for completeness)
    database_url: str = ""
    redis_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    # Decide mock mode: explicit MOCK_LLM env wins; otherwise mock when we have
    # no API key so the pipeline still runs.
    explicit = os.environ.get("MOCK_LLM")
    s.mock_llm = _str_to_bool(explicit, default=not bool(s.openai_api_key))
    return s


settings = get_settings()
