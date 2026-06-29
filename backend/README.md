# Backend — Agent Infrastructure SaaS

FastAPI service running a 6-agent LangGraph pipeline:

**Planner → Infrastructure → Cost** (budget feedback loop) → *approval gate* →
**Deploy → Monitoring → Optimization**.

## Setup (Poetry)

```bash
cd backend
poetry install              # creates backend/.venv and installs deps
poetry run uvicorn main:app --reload --port 8000
```

## LLM mode

The agents call OpenAI when `OPENAI_API_KEY` is set in the repo-root
`.env.local`. With no key the pipeline falls back to a deterministic mock so it
still runs offline. Force a mode with `MOCK_LLM=true|false`. Tests always run in
mock mode (see `tests/conftest.py`), so they need no key and cost nothing.

```bash
poetry run pytest -q
```

## Layout

```
agent/
  state.py            # shared GraphState
  orchestrator.py     # the two LangGraph graphs + run_plan / run_deploy
  agents/             # one node per agent (planner, infrastructure, cost, ...)
llm/factory.py        # configured ChatOpenAI / embeddings
observability/        # logging
config.py             # settings (.env.local) + mock-mode decision
main.py               # FastAPI app + session endpoints
```
