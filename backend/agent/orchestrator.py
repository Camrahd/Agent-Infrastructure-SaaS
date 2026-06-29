"""LangGraph orchestration for the multi-agent pipeline.

The pipeline is split into two graphs around the human approval gate:

* **plan graph** — Planner → Infrastructure → Cost, with a feedback loop back
  to Infrastructure while the design is over budget (bounded by
  ``settings.max_redesigns``).
* **deploy graph** — Deploy → Monitoring → Optimization, run only after the
  user approves the plan.

Both graphs are compiled once at import and exposed through ``run_plan`` /
``run_deploy`` convenience wrappers that the FastAPI layer calls.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.agents import (
    cost_node,
    deploy_node,
    infrastructure_node,
    monitoring_node,
    optimization_node,
    planner_node,
)
from agent.state import GraphState
from config import settings
from observability.logger import get_logger

logger = get_logger(__name__)


def _budget_router(state: GraphState) -> str:
    """After Cost: loop back to Infrastructure if over budget, else finish."""
    cost = state.get("cost", {})
    within = bool(cost.get("within_budget", True))
    redesigns = state.get("redesign_count", 0)
    if not within and redesigns < settings.max_redesigns:
        logger.info("cost over budget; redesign %d/%d", redesigns + 1, settings.max_redesigns)
        return "redesign"
    return "done"


def _bump_redesign(state: GraphState) -> dict[str, Any]:
    """Tiny node that increments the redesign counter before re-running infra."""
    return {"redesign_count": state.get("redesign_count", 0) + 1}


@lru_cache(maxsize=1)
def build_plan_graph():
    g = StateGraph(GraphState)
    g.add_node("planner", planner_node)
    g.add_node("infrastructure", infrastructure_node)
    g.add_node("cost", cost_node)
    g.add_node("bump_redesign", _bump_redesign)

    g.add_edge(START, "planner")
    g.add_edge("planner", "infrastructure")
    g.add_edge("infrastructure", "cost")
    g.add_conditional_edges(
        "cost",
        _budget_router,
        {"redesign": "bump_redesign", "done": END},
    )
    g.add_edge("bump_redesign", "infrastructure")
    return g.compile()


@lru_cache(maxsize=1)
def build_deploy_graph():
    g = StateGraph(GraphState)
    g.add_node("deploy", deploy_node)
    g.add_node("monitoring", monitoring_node)
    g.add_node("optimization", optimization_node)

    g.add_edge(START, "deploy")
    g.add_edge("deploy", "monitoring")
    g.add_edge("monitoring", "optimization")
    g.add_edge("optimization", END)
    return g.compile()


def run_plan(user_input: str) -> GraphState:
    """Run Planner → Infrastructure → Cost (with budget feedback loop)."""
    initial: GraphState = {"user_input": user_input, "steps": [], "errors": [], "redesign_history": []}
    return build_plan_graph().invoke(initial)


def run_deploy(state: GraphState) -> GraphState:
    """Run Deploy → Monitoring → Optimization on an approved plan state."""
    return build_deploy_graph().invoke(state)
