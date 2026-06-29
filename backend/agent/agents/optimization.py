"""Optimization agent — monitoring + cost → actionable recommendations."""
from __future__ import annotations

import json
from typing import Any

from agent.agents.base import run_json_agent
from agent.state import GraphState

SYSTEM_PROMPT = """You are the Optimization Agent. Given monitoring metrics and
a cost breakdown, find performance bottlenecks and cost anomalies and propose
concrete, actionable optimizations. Each recommendation must include an
estimated monthly saving.

Return ONLY a JSON object with exactly these keys:
{
  "recommendations": [
    {
      "title": string,
      "category": "llm"|"infra"|"external_api"|"performance",
      "rationale": string,
      "projected_savings_usd_monthly": number,
      "projected_savings_pct": number,
      "effort": "low"|"medium"|"high"
    }
  ],
  "total_projected_savings_usd_monthly": number,
  "summary": string
}
"""


def _mock_recommendations(cost: dict[str, Any], monitoring: dict[str, Any]) -> dict[str, Any]:
    llm_total = float(cost.get("llm_total_usd", 300) or 300)
    infra_total = float(cost.get("infra_total_usd", 200) or 200)
    recs: list[dict[str, Any]] = []

    # Driven by the simulated alerts/metrics so the advice tracks the data.
    llm = monitoring.get("llm_tokens", {})
    if llm.get("prompt_tokens_per_min", 0) > 2 * llm.get("completion_tokens_per_min", 1):
        recs.append({
            "title": "Compress the system prompt / use prompt caching",
            "category": "llm",
            "rationale": "Prompt tokens are >2x completion tokens; trimming context cuts spend directly.",
            "projected_savings_usd_monthly": round(llm_total * 0.20, 2),
            "projected_savings_pct": 20,
            "effort": "low",
        })
    recs.append({
        "title": "Route classification/extraction calls to gpt-4o-mini",
        "category": "llm",
        "rationale": "Cheaper model is sufficient for structured sub-tasks; reserve gpt-4o for hard reasoning.",
        "projected_savings_usd_monthly": round(llm_total * 0.40, 2),
        "projected_savings_pct": 40,
        "effort": "low",
    })
    if any(a.get("type") == "latency_breach" for a in monitoring.get("alerts", [])):
        recs.append({
            "title": "Add a Redis response cache for repeated queries",
            "category": "performance",
            "rationale": "Peak latency breaches the target; caching hot queries cuts both latency and LLM calls.",
            "projected_savings_usd_monthly": round(llm_total * 0.15, 2),
            "projected_savings_pct": 15,
            "effort": "medium",
        })
    recs.append({
        "title": "Use 1-year reserved/savings-plan pricing for steady ECS+RDS load",
        "category": "infra",
        "rationale": "Baseline compute runs 24/7; reserved pricing saves ~30% vs on-demand.",
        "projected_savings_usd_monthly": round(infra_total * 0.30, 2),
        "projected_savings_pct": 30,
        "effort": "low",
    })

    total = round(sum(r["projected_savings_usd_monthly"] for r in recs), 2)
    return {
        "recommendations": recs,
        "total_projected_savings_usd_monthly": total,
        "summary": f"{len(recs)} optimizations identified; projected savings ~${total:,.0f}/month.",
    }


def optimization_node(state: GraphState) -> dict[str, Any]:
    cost = state.get("cost", {})
    monitoring = state.get("monitoring", {})
    result = run_json_agent(
        name="optimization",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=(
            f"Cost breakdown:\n{json.dumps(cost, indent=2)}\n\n"
            f"Monitoring metrics:\n{json.dumps(monitoring, indent=2)}"
        ),
        mock_payload=lambda: _mock_recommendations(cost, monitoring),
    )
    return {"optimization": result, "steps": [{"agent": "optimization", "output": result}]}
