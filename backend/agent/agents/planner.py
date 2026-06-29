"""Planner agent — natural language requirements → structured spec."""
from __future__ import annotations

import re
from typing import Any

from agent.agents.base import run_json_agent
from agent.state import GraphState

SYSTEM_PROMPT = """You are the Planner Agent in an infrastructure-design platform.
Convert the user's natural-language application requirements into a structured
specification. Infer sensible defaults where the user is silent, and say so.

Return ONLY a JSON object with exactly these keys:
{
  "application_type": string,            // e.g. "RAG", "chatbot", "API", "batch"
  "users_per_day": integer,
  "latency_requirement_seconds": number,
  "budget_usd_monthly": number,
  "document_count": integer,             // 0 if not applicable
  "preferred_llm_provider": string,      // e.g. "OpenAI", "Anthropic", "any"
  "constraints": [string],
  "summary": string                      // one sentence restating the goal
}
"""


def _heuristic_spec(text: str) -> dict[str, Any]:
    """Cheap deterministic parse used in mock mode (no LLM)."""
    lowered = text.lower()

    def _num(pattern: str, default: float) -> float:
        m = re.search(pattern, lowered)
        if not m:
            return default
        raw = m.group(1).replace(",", "").replace("k", "000").replace("m", "000000")
        try:
            return float(raw)
        except ValueError:
            return default

    users = int(_num(r"([\d,]+\s*[km]?)\s*(?:daily\s*)?users", 10000))
    docs = int(_num(r"([\d,]+\s*[km]?)\s*(?:documents|docs)", 1_000_000 if "rag" in lowered else 0))
    latency = _num(r"(?:latency|response)[^\d]*([\d.]+)\s*s", 2.0)
    budget = _num(r"\$?\s*([\d,]+\s*[km]?)\s*(?:/?\s*month|per month|monthly|budget)", 1000)

    if "rag" in lowered:
        app_type = "RAG"
    elif "chat" in lowered:
        app_type = "chatbot"
    elif "api" in lowered:
        app_type = "API"
    else:
        app_type = "web application"

    if "anthropic" in lowered or "claude" in lowered:
        provider = "Anthropic"
    elif "openai" in lowered or "gpt" in lowered:
        provider = "OpenAI"
    else:
        provider = "OpenAI"

    return {
        "application_type": app_type,
        "users_per_day": users,
        "latency_requirement_seconds": latency,
        "budget_usd_monthly": budget,
        "document_count": docs,
        "preferred_llm_provider": provider,
        "constraints": [c for c in [
            f"latency < {latency:g}s" if latency else "",
            f"budget < ${budget:,.0f}/month" if budget else "",
        ] if c],
        "summary": f"Build a {app_type} for ~{users:,} users/day within ${budget:,.0f}/month.",
    }


def planner_node(state: GraphState) -> dict[str, Any]:
    user_input = state["user_input"]
    spec = run_json_agent(
        name="planner",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"User requirements:\n{user_input}",
        mock_payload=lambda: _heuristic_spec(user_input),
    )
    return {
        "requirements": spec,
        "redesign_count": 0,
        "steps": [{"agent": "planner", "output": spec}],
    }
