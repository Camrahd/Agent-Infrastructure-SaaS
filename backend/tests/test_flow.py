"""End-to-end flow tests for the multi-agent pipeline (mock-LLM mode).

Covers the orchestrator graphs directly and the full FastAPI request flow,
including the cost>budget feedback loop and the approval gate.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from agent.orchestrator import run_deploy, run_plan
from main import app

client = TestClient(app)

RAG_REQUIREMENTS = (
    "We're building a RAG chatbot for 10,000 daily users with sub-2s latency, "
    "storing 1 million documents, budget under $1000/month using OpenAI models."
)


def test_plan_graph_produces_three_agent_outputs():
    state = run_plan(RAG_REQUIREMENTS)
    assert state["requirements"]["application_type"] == "RAG"
    assert state["requirements"]["users_per_day"] == 10000
    assert "components" in state["infrastructure"]
    assert "total_monthly_usd" in state["cost"]
    # Planner + at least one infra + one cost step recorded.
    agents = [s["agent"] for s in state["steps"]]
    assert agents[0] == "planner"
    assert "infrastructure" in agents and "cost" in agents


def test_budget_feedback_loop_redesigns_and_converges():
    state = run_plan(RAG_REQUIREMENTS)
    # First mock cost pass is over budget, so the loop must have redesigned.
    assert state["redesign_count"] >= 1
    # After redesign the final cost should be within budget.
    assert state["cost"]["within_budget"] is True
    assert state["cost"]["total_monthly_usd"] <= state["cost"]["budget_usd"]


def test_deploy_phase_runs_all_three_agents():
    plan = run_plan(RAG_REQUIREMENTS)
    final = run_deploy(plan)
    assert "docker_compose" in final["deployment"]["artifacts"]
    assert "terraform" in final["deployment"]["artifacts"]
    assert "timeseries" in final["monitoring"]
    assert len(final["monitoring"]["timeseries"]) > 0
    assert final["optimization"]["recommendations"]
    assert final["optimization"]["total_projected_savings_usd_monthly"] > 0


def test_api_full_flow_with_approval_gate():
    # Health check reports mock mode.
    health = client.get("/health").json()
    assert health["mock_llm"] is True

    # 1. Create session -> plan phase.
    resp = client.post("/api/sessions", json={"requirements": RAG_REQUIREMENTS})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sid = body["session_id"]
    assert body["status"] == "planned"
    assert body["requirements"] and body["infrastructure"] and body["cost"]
    # Deploy outputs not present until approved.
    assert body["deployment"] is None
    assert body["monitoring"] is None

    # 2. Fetch session.
    got = client.get(f"/api/sessions/{sid}").json()
    assert got["session_id"] == sid

    # 3. Approve -> deploy phase.
    approved = client.post(f"/api/sessions/{sid}/approve").json()
    assert approved["status"] == "deployed"
    assert approved["deployment"]["artifacts"]["terraform"]
    assert approved["monitoring"]["alerts"] is not None
    assert approved["optimization"]["recommendations"]


def test_unknown_session_returns_404():
    assert client.get("/api/sessions/does-not-exist").status_code == 404
    assert client.post("/api/sessions/nope/approve").status_code == 404
