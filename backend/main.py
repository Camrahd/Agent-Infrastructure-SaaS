"""FastAPI entrypoint for the Agent Infrastructure SaaS backend.

Exposes the multi-agent pipeline as a small session-oriented API:

    POST /api/sessions              -> run Planner→Infra→Cost, create a session
    GET  /api/sessions/{id}         -> fetch current session state
    POST /api/sessions/{id}/approve -> run Deploy→Monitoring→Optimization
    GET  /health                    -> liveness + which LLM mode is active

Session state lives in an in-process dict — fine for local dev / demos. Swap
for Redis/Postgres when persistence across processes is needed.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.orchestrator import run_deploy, run_plan
from config import settings
from observability.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Agent Infrastructure SaaS",
    description="Multi-agent infrastructure design, costing, deployment, monitoring and optimization.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> GraphState (plus a small status field)
_SESSIONS: dict[str, dict[str, Any]] = {}


class CreateSessionRequest(BaseModel):
    requirements: str = Field(..., min_length=3, description="Natural-language application requirements.")


class SessionResponse(BaseModel):
    session_id: str
    status: str  # "planned" | "deployed"
    mock_llm: bool
    requirements: dict[str, Any] | None = None
    infrastructure: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None
    monitoring: dict[str, Any] | None = None
    optimization: dict[str, Any] | None = None
    redesign_count: int = 0
    steps: list[dict[str, Any]] = []
    errors: list[str] = []


def _to_response(session_id: str, state: dict[str, Any]) -> SessionResponse:
    return SessionResponse(
        session_id=session_id,
        status=state.get("_status", "planned"),
        mock_llm=settings.mock_llm,
        requirements=state.get("requirements"),
        infrastructure=state.get("infrastructure"),
        cost=state.get("cost"),
        deployment=state.get("deployment"),
        monitoring=state.get("monitoring"),
        optimization=state.get("optimization"),
        redesign_count=state.get("redesign_count", 0),
        steps=state.get("steps", []),
        errors=state.get("errors", []),
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "mock_llm": settings.mock_llm, "max_redesigns": settings.max_redesigns}


@app.post("/api/sessions", response_model=SessionResponse)
def create_session(req: CreateSessionRequest) -> SessionResponse:
    """Run the plan phase (Planner → Infrastructure → Cost) and store the result."""
    try:
        state = dict(run_plan(req.requirements))
    except Exception as exc:  # surface a clean 502 rather than a stack trace
        logger.exception("plan phase failed")
        raise HTTPException(status_code=502, detail=f"Plan phase failed: {exc}") from exc

    session_id = uuid.uuid4().hex
    state["_status"] = "planned"
    _SESSIONS[session_id] = state
    logger.info("created session %s (mock_llm=%s)", session_id, settings.mock_llm)
    return _to_response(session_id, state)


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_response(session_id, state)


@app.post("/api/sessions/{session_id}/approve", response_model=SessionResponse)
def approve_session(session_id: str) -> SessionResponse:
    """Approve the plan and run the deploy phase (Deploy → Monitoring → Optimization)."""
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if state.get("_status") == "deployed":
        return _to_response(session_id, state)  # idempotent

    state["approved"] = True
    try:
        new_state = dict(run_deploy(state))
    except Exception as exc:
        logger.exception("deploy phase failed")
        raise HTTPException(status_code=502, detail=f"Deploy phase failed: {exc}") from exc

    new_state["_status"] = "deployed"
    _SESSIONS[session_id] = new_state
    logger.info("approved + deployed session %s", session_id)
    return _to_response(session_id, new_state)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=settings.debug)
