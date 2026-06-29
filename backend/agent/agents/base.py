"""Shared helpers for agent nodes.

Every agent node turns some slice of ``GraphState`` into a structured JSON
object. To keep the nodes small they all go through :func:`run_json_agent`,
which has two modes:

* **real** — build a chat prompt, call the configured OpenAI model, and parse
  the JSON object out of the reply (tolerating Markdown code fences and minor
  preamble).
* **mock** — skip the network entirely and return a caller-supplied payload.
  This makes the whole pipeline runnable and deterministically testable with
  no API key and no cost.

The mode is decided once from :data:`config.settings.mock_llm`.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from config import settings
from observability.logger import get_logger

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _safe_json_extract(text: str) -> dict[str, Any] | list[Any]:
    """Best-effort extraction of a JSON value from an LLM reply.

    Handles three common shapes: a bare JSON document, a ```json fenced block,
    or JSON embedded in prose. Raises ``ValueError`` if nothing parses.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("empty model response")

    # 1. Whole string is JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Fenced ```json block.
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    # 3. First {...} or [...] span in the text.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"could not parse JSON from model response: {text[:200]!r}")


def run_json_agent(
    *,
    name: str,
    system_prompt: str,
    user_prompt: str,
    mock_payload: dict[str, Any] | Callable[[], dict[str, Any]],
    temperature: float | None = None,
) -> dict[str, Any]:
    """Run one agent turn and return a parsed JSON object.

    Args:
        name: Agent name, used only for logging.
        system_prompt: System instruction describing the agent's role and the
            exact JSON schema it must return.
        user_prompt: The task input (typically serialized upstream state).
        mock_payload: The dict to return when mock mode is on. May be a
            zero-arg callable so callers can compute it lazily.
        temperature: Optional per-call temperature override.

    Returns:
        The parsed JSON object the agent produced.
    """
    if settings.mock_llm:
        payload = mock_payload() if callable(mock_payload) else mock_payload
        logger.info("agent %s ran in MOCK mode", name)
        return payload

    # Imported lazily so mock-mode/tests never require langchain-openai or a key.
    from langchain_core.messages import HumanMessage, SystemMessage

    from llm.factory import get_llm

    llm = get_llm(temperature=temperature) if temperature is not None else get_llm()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    last_err: Exception | None = None
    for attempt in range(2):
        response = llm.invoke(messages)
        text = response.content if isinstance(response.content, str) else str(response.content)
        try:
            result = _safe_json_extract(text)
        except ValueError as exc:
            last_err = exc
            logger.warning("agent %s returned unparseable JSON (attempt %d): %s", name, attempt + 1, exc)
            messages.append(HumanMessage(content="Return ONLY a valid JSON object, no prose, no code fences."))
            continue
        if not isinstance(result, dict):
            last_err = ValueError("expected a JSON object")
            messages.append(HumanMessage(content="Return a JSON object (not a list or scalar)."))
            continue
        logger.info("agent %s ran in LIVE mode", name)
        return result

    raise RuntimeError(f"agent {name} failed to produce valid JSON: {last_err}")
