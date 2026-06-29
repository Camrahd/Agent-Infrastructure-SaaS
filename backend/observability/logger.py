"""Structured logging helpers for the backend.

Exports a single ``get_logger`` helper that returns a standard library logger
configured with a readable format for local development. All agent modules
should import their logger from here so log output is consistent across the
service.
"""
from __future__ import annotations

import logging
import sys
from typing import TextIO

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DEFAULT_LEVEL = logging.INFO


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for ``name``.

    The logger is created once per name, has propagation enabled, and is
    attached to a ``StreamHandler`` writing to ``stderr`` when no handlers are
    already present. This makes logs visible immediately in both local runs
    and test output without requiring external configuration.

    Args:
        name: The dotted module name, conventionally ``__name__``.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(_DEFAULT_LEVEL)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(_DEFAULT_LEVEL)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)

    return logger


def configure_logging(
    level: int | str = _DEFAULT_LEVEL,
    stream: TextIO = sys.stderr,
    fmt: str | None = None,
) -> None:
    """Configure the root logger for the application.

    This is a convenience helper for entry points (``main.py``, uvicorn,
    pytest conftest, etc.) that want to set a uniform format and level on
    all log output.

    Args:
        level: Logging level (e.g. ``logging.INFO`` or ``"DEBUG"``).
        stream: Output stream, defaults to ``stderr``.
        fmt: Optional override format string.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper())

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicate output.
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt or _DEFAULT_FORMAT))
    root.addHandler(handler)
