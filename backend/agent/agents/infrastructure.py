"""Infrastructure agent — structured spec → infrastructure design.

On a redesign pass (triggered when the Cost agent finds the design over budget)
it receives the previous design plus cost feedback and must produce a cheaper
architecture.
"""
from __future__ import annotations

import json
from typing import Any

from agent.agents.base import run_json_agent
from agent.state import GraphState

SYSTEM_PROMPT = """You are the Infrastructure Agent. Design an optimal cloud
architecture for the given application specification. Prefer managed services
for reliability but surface the trade-offs. If redesign feedback is provided,
return a CHEAPER design that still meets the requirements.

Return ONLY a JSON object with exactly these keys:
{
  "components": {
    "frontend": string, "backend": string, "database": string,
    "cache": string, "vector_db": string, "cloud": string
  },
  "scaling_strategy": string,
  "tradeoffs": [
    {"decision": string, "chosen": string, "alternative": string, "rationale": string}
  ],
  "tier": "cost-optimized" | "balanced" | "performance",
  "notes": string
}
"""


def _mock_design(spec: dict[str, Any], redesign: int) -> dict[str, Any]:
    """Two deterministic designs: a richer default, then a cheaper redesign."""
    cost_optimized = redesign > 0
    if cost_optimized:
        components = {
            "frontend": "Next.js on Vercel (Hobby)",
            "backend": "FastAPI on a single AWS ECS Fargate task (0.5 vCPU)",
            "database": "PostgreSQL on AWS RDS (db.t4g.micro)",
            "cache": "Redis on a small ElastiCache node",
            "vector_db": "Self-hosted Qdrant on the ECS task",
            "cloud": "AWS",
        }
        return {
            "components": components,
            "scaling_strategy": "Single task with manual scale-up; cache aggressively to cut LLM calls.",
            "tradeoffs": [
                {
                    "decision": "Vector database",
                    "chosen": "Self-hosted Qdrant",
                    "alternative": "Managed Pinecone",
                    "rationale": "Removes a per-month managed fee to fit the budget; costs ops effort.",
                },
            ],
            "tier": "cost-optimized",
            "notes": "Redesigned for cost: dropped managed Pinecone and downsized compute.",
        }
    components = {
        "frontend": "Next.js on Vercel",
        "backend": "FastAPI on AWS ECS Fargate (2 tasks, 1 vCPU each)",
        "database": "PostgreSQL on AWS RDS (db.t4g.medium, Multi-AZ)",
        "cache": "Redis on AWS ElastiCache",
        "vector_db": "Pinecone (managed)",
        "cloud": "AWS",
    }
    return {
        "components": components,
        "scaling_strategy": "Horizontal autoscaling on ECS (2–6 tasks) behind an ALB; "
        f"sized for ~{spec.get('users_per_day', 0):,} users/day under "
        f"{spec.get('latency_requirement_seconds', 2)}s latency.",
        "tradeoffs": [
            {
                "decision": "Compute",
                "chosen": "ECS Fargate (managed)",
                "alternative": "Self-managed EC2",
                "rationale": "Lower ops burden at a modest price premium.",
            },
            {
                "decision": "Vector database",
                "chosen": "Pinecone (managed)",
                "alternative": "Self-hosted Qdrant",
                "rationale": "Faster to ship and scales automatically; higher monthly cost.",
            },
        ],
        "tier": "balanced",
        "notes": "Balanced managed-services design meeting latency and scale targets.",
    }


def infrastructure_node(state: GraphState) -> dict[str, Any]:
    spec = state["requirements"]
    redesign = state.get("redesign_count", 0)
    prev_cost = state.get("cost")

    feedback = ""
    if redesign > 0 and prev_cost:
        feedback = (
            "\n\nREDESIGN REQUIRED — the previous design was over budget.\n"
            f"Previous total: ${prev_cost.get('total_monthly_usd')}/month vs budget "
            f"${spec.get('budget_usd_monthly')}/month.\n"
            f"Previous design: {json.dumps(state.get('infrastructure', {}))}\n"
            "Produce a cheaper architecture."
        )

    design = run_json_agent(
        name="infrastructure",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"Application specification:\n{json.dumps(spec, indent=2)}{feedback}",
        mock_payload=lambda: _mock_design(spec, redesign),
    )
    step = {"agent": "infrastructure", "output": design}
    if redesign > 0:
        step["redesign_pass"] = redesign
    return {"infrastructure": design, "steps": [step]}
