# Running locally

A Next.js frontend talks to a FastAPI backend that runs a 6-agent LangGraph
pipeline: **Planner → Infrastructure → Cost** (with a budget feedback loop) →
*approval gate* → **Deploy → Monitoring → Optimization**.

## LLM mode

With an `OPENAI_API_KEY` set in the repo-root `.env.local`, every reasoning
agent (Planner, Infrastructure, Cost, Optimization) calls **live OpenAI** — this
is the default. With no key the pipeline falls back to a deterministic mock so
it still runs offline. Force a mode with `MOCK_LLM=true|false`.

> The **Monitoring** agent's metrics are *simulated* — there is no real deployed
> infrastructure to scrape. The **Deploy** agent emits real, valid IaC files.

## Backend (port 8000) — Poetry

```bash
cd backend
poetry install                                   # creates backend/.venv
poetry run uvicorn main:app --reload --port 8000
```

Run the flow tests (mock mode is forced in tests, so no key / cost):

```bash
cd backend && poetry run pytest -q
```

### Endpoints

| Method | Path                          | Purpose                                   |
|--------|-------------------------------|-------------------------------------------|
| GET    | `/health`                     | Liveness + which LLM mode is active       |
| POST   | `/api/sessions`               | Plan phase (Planner→Infra→Cost), new session |
| GET    | `/api/sessions/{id}`          | Fetch current session state               |
| POST   | `/api/sessions/{id}/approve`  | Approve → Deploy→Monitoring→Optimization  |

## Frontend (port 3000)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The API base is configured in
`frontend/.env.local` (`NEXT_PUBLIC_API_BASE=http://localhost:8000`).

## Flow

1. Enter natural-language requirements (an example is prefilled).
2. **Generate Plan** runs Planner → Infrastructure → Cost; if the estimate is
   over budget the Infrastructure agent is re-run (up to `MAX_REDESIGNS`, default 2)
   until it fits.
3. Review the structured plan, then **Approve & Deploy**.
4. The Deploy agent emits Docker/Terraform/K8s artifacts; the Monitoring agent
   shows simulated metrics, token-budget tracking and alerts; the Optimization
   agent lists recommendations with projected savings.
