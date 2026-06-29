"""Cost agent — infrastructure design → cost breakdown vs budget.

Emits ``within_budget``; the orchestrator uses it to decide whether to loop
back to the Infrastructure agent for a cheaper redesign.
"""
from __future__ import annotations

import json
from typing import Any

from agent.agents.base import run_json_agent
from agent.state import GraphState

SYSTEM_PROMPT = """You are the Cost Agent. Estimate the monthly cost of the
given infrastructure design. Track three categories independently: infra, LLM
tokens, and external API tokens. Compare the total against the stated budget.

Return ONLY a JSON object with exactly these keys:
{
  "breakdown": [{"category": "infra"|"llm"|"external_api", "item": string, "monthly_usd": number}],
  "infra_total_usd": number,
  "llm_total_usd": number,
  "external_api_total_usd": number,
  "total_monthly_usd": number,
  "budget_usd": number,
  "within_budget": boolean,
  "notes": string
}
"""


def _mock_cost(spec: dict[str, Any], infra: dict[str, Any], redesign: int) -> dict[str, Any]:
    """First pass is intentionally over budget to exercise the feedback loop;
    the cheaper redesign comes in under budget."""
    budget = float(spec.get("budget_usd_monthly", 1000) or 1000)
    if infra.get("tier") == "cost-optimized" or redesign > 0:
        breakdown = [
            {"category": "infra", "item": "ECS Fargate (1 task)", "monthly_usd": 90},
            {"category": "infra", "item": "RDS db.t4g.micro", "monthly_usd": 60},
            {"category": "infra", "item": "ElastiCache (small)", "monthly_usd": 35},
            {"category": "infra", "item": "Self-hosted Qdrant", "monthly_usd": 0},
            {"category": "llm", "item": "OpenAI gpt-4o-mini", "monthly_usd": 220},
            {"category": "external_api", "item": "Embeddings + misc APIs", "monthly_usd": 60},
        ]
    else:
        breakdown = [
            {"category": "infra", "item": "ECS Fargate (2 tasks)", "monthly_usd": 200},
            {"category": "infra", "item": "RDS db.t4g.medium Multi-AZ", "monthly_usd": 150},
            {"category": "infra", "item": "ElastiCache Redis", "monthly_usd": 50},
            {"category": "infra", "item": "Pinecone (managed)", "monthly_usd": 70},
            {"category": "llm", "item": "OpenAI gpt-4o", "monthly_usd": 480},
            {"category": "external_api", "item": "Embeddings + misc APIs", "monthly_usd": 120},
        ]

    infra_total = sum(b["monthly_usd"] for b in breakdown if b["category"] == "infra")
    llm_total = sum(b["monthly_usd"] for b in breakdown if b["category"] == "llm")
    api_total = sum(b["monthly_usd"] for b in breakdown if b["category"] == "external_api")
    total = infra_total + llm_total + api_total

    return {
        "breakdown": breakdown,
        "infra_total_usd": infra_total,
        "llm_total_usd": llm_total,
        "external_api_total_usd": api_total,
        "total_monthly_usd": total,
        "budget_usd": budget,
        "within_budget": total <= budget,
        "notes": (
            f"Estimated ${total:,.0f}/month vs ${budget:,.0f} budget — "
            + ("within budget." if total <= budget else "OVER budget; redesign recommended.")
        ),
    }


def cost_node(state: GraphState) -> dict[str, Any]:
    spec = state["requirements"]
    infra = state["infrastructure"]
    redesign = state.get("redesign_count", 0)

    cost = run_json_agent(
        name="cost",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=(
            f"Budget: ${spec.get('budget_usd_monthly')}/month\n"
            f"Application spec:\n{json.dumps(spec, indent=2)}\n\n"
            f"Infrastructure design:\n{json.dumps(infra, indent=2)}"
        ),
        mock_payload=lambda: _mock_cost(spec, infra, redesign),
    )
    _normalize(cost, spec)
    return {"cost": cost, "steps": [{"agent": "cost", "output": cost}]}


def _normalize(cost: dict[str, Any], spec: dict[str, Any]) -> None:
    """Make the budget verdict authoritative regardless of what the LLM wrote.

    The orchestrator's feedback loop keys off ``within_budget``, so we derive it
    (and the category/grand totals) from the line items rather than trusting the
    model to do arithmetic. This keeps the redesign loop correct on live data.
    """
    breakdown = cost.get("breakdown") or []

    def _cat_total(cat: str) -> float:
        return float(sum(b.get("monthly_usd", 0) or 0 for b in breakdown if b.get("category") == cat))

    if breakdown:
        cost["infra_total_usd"] = round(_cat_total("infra"), 2)
        cost["llm_total_usd"] = round(_cat_total("llm"), 2)
        cost["external_api_total_usd"] = round(_cat_total("external_api"), 2)
        cost["total_monthly_usd"] = round(
            cost["infra_total_usd"] + cost["llm_total_usd"] + cost["external_api_total_usd"], 2
        )

    budget = float(spec.get("budget_usd_monthly") or cost.get("budget_usd") or 0)
    cost["budget_usd"] = budget
    total = float(cost.get("total_monthly_usd") or 0)
    cost["within_budget"] = budget <= 0 or total <= budget
