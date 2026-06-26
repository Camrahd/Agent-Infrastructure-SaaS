"""LLM and embedding model factory.

Loads defaults from ``config.yaml`` in this directory and returns configured
model instances. API keys are read from environment variables
(``OPENAI_API_KEY``) and are never committed to the repo.

Usage::

    from llm.factory import get_llm, get_embedding_model

    llm = get_llm()                                # config defaults
    llm = get_llm(model="gpt-4o", temperature=0.7) # per-call overrides
    embedder = get_embedding_model()
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    """Load and cache the YAML config file once per process."""
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid config at {_CONFIG_PATH}: expected a YAML mapping at the top level"
        )
    return data


def _require_api_key(env_var: str = "OPENAI_API_KEY") -> str:
    key = os.environ.get(env_var)
    if not key:
        raise RuntimeError(
            f"{env_var} environment variable is not set; add it to your .env "
            "(see .env.example) or export it before starting the backend."
        )
    return key


def get_llm(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    **overrides: Any,
) -> BaseChatModel:
    """Return a configured chat LLM.

    Defaults come from the ``llm`` section of ``config.yaml``. Any explicit
    keyword argument overrides the config value. The API key is read from the
    ``OPENAI_API_KEY`` environment variable.
    """
    cfg = _load_config().get("llm", {})

    selected_provider = provider or cfg.get("provider", "openai")
    if selected_provider != "openai":
        raise ValueError(
            f"Unsupported LLM provider: {selected_provider!r}. "
            "Only 'openai' is currently wired up; add a branch here to extend."
        )

    kwargs: dict[str, Any] = {
        "model": model or cfg.get("model", "gpt-4o-mini"),
        "temperature": (
            temperature if temperature is not None else cfg.get("temperature", 0.0)
        ),
        "max_tokens": cfg.get("max_tokens"),
        "timeout": cfg.get("timeout"),
        "max_retries": cfg.get("max_retries"),
        "api_key": _require_api_key(),
    }
    # Drop unset optional fields so langchain-openai applies its own defaults.
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    kwargs.update(overrides)
    return ChatOpenAI(**kwargs)


def get_embedding_model(
    *,
    provider: str | None = None,
    model: str | None = None,
    **overrides: Any,
) -> Embeddings:
    """Return a configured embedding model.

    Defaults come from the ``embedding`` section of ``config.yaml``. Any
    explicit keyword argument overrides the config value. The API key is read
    from the ``OPENAI_API_KEY`` environment variable.
    """
    cfg = _load_config().get("embedding", {})

    selected_provider = provider or cfg.get("provider", "openai")
    if selected_provider != "openai":
        raise ValueError(
            f"Unsupported embedding provider: {selected_provider!r}. "
            "Only 'openai' is currently wired up; add a branch here to extend."
        )

    kwargs: dict[str, Any] = {
        "model": model or cfg.get("model", "text-embedding-3-small"),
        "dimensions": cfg.get("dimensions"),
        "api_key": _require_api_key(),
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    kwargs.update(overrides)
    return OpenAIEmbeddings(**kwargs)
