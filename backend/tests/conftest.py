"""Force mock-LLM mode for the whole test session.

Set before any backend module is imported so ``config.get_settings`` (cached)
picks it up. This keeps tests free, deterministic, and offline.
"""
import os

os.environ["MOCK_LLM"] = "true"
