"""Shared LangGraph state for the multi-agent pipeline.

A single ``GraphState`` flows through every agent node. Each node reads the
fields it needs and returns a partial dict that LangGraph merges back in. The
``steps`` list is an append-only audit trail used by the API/UI to show what
each agent produced and in what order.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class GraphState(TypedDict, total=False):
    # Input
    user_input: str

    # Agent outputs (plan phase)
    requirements: dict[str, Any]
    infrastructure: dict[str, Any]
    cost: dict[str, Any]
    redesign_count: int
    redesign_history: Annotated[list[dict[str, Any]], operator.add]

    # Approval gate
    approved: bool

    # Agent outputs (deploy phase)
    deployment: dict[str, Any]
    monitoring: dict[str, Any]
    optimization: dict[str, Any]

    # Audit trail + errors (append-only across nodes)
    steps: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
