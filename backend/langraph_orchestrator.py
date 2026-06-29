# ============================================================
# langgraph_orchestrator.py
# ============================================================

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# ============================================================
# 1. SHARED STATE
#    Every agent reads from and writes to this dict.
#    LangGraph merges the returned dict into the running state.
# ============================================================

class AgentState(TypedDict):
    # --- inputs ---
    user_input: str                        # raw NL requirement

    # --- planner output ---
    project_spec: Optional[dict]           # structured requirements

    # --- infra output ---
    infra_design: Optional[dict]           # chosen stack
    infra_iteration: int                   # how many re-designs so far

    # --- cost output ---
    cost_estimate: Optional[dict]          # breakdown + total
    within_budget: Optional[bool]          # gate for conditional edge

    # --- deploy output ---
    deployment_configs: Optional[dict]     # terraform / docker artefacts

    # --- monitoring output ---
    metrics: Optional[dict]                # live compute + token stats

    # --- optimization output ---
    recommendations: Optional[list]        # actionable suggestions


# ============================================================
# 2. AGENT NODES
#    Each node receives the full state, does its work
#    (calls the LLM, an API, etc.), and returns a PARTIAL
#    dict — LangGraph merges it into state automatically.
# ============================================================

def planner_agent(state: AgentState) -> dict:
    """Convert raw NL input → structured project spec."""
    prompt = f"""
    You are a technical product manager. Parse this requirement into JSON.

    Requirement: {state['user_input']}

    Return JSON with keys:
    application_type, users_per_day, latency_requirement_seconds,
    budget_usd_per_month, storage_documents, preferred_llm_provider
    """
    response = llm.invoke(prompt)
    import json, re
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    spec = json.loads(match.group()) if match else {}
    print(f"[Planner] Parsed spec: {spec}")
    return {"project_spec": spec}


def infrastructure_agent(state: AgentState) -> dict:
    """Design the optimal cloud stack for the spec."""
    iteration = state.get("infra_iteration", 0)
    cost_hint = ""
    if iteration > 0:
        prev_cost = state.get("cost_estimate", {}).get("total_monthly_usd", 0)
        budget    = state["project_spec"].get("budget_usd_per_month", 1000)
        cost_hint = (
            f"\n⚠️  Previous design cost ${prev_cost}/mo, "
            f"budget is ${budget}/mo. Suggest cheaper alternatives "
            f"(smaller instances, self-hosted instead of managed, etc.)."
        )

    prompt = f"""
    You are a cloud architect. Design infrastructure for:
    {state['project_spec']}
    {cost_hint}

    Return JSON with keys:
    frontend, backend, database, cache, vector_db,
    cloud_provider, compute_type, scaling_strategy,
    trade_offs (list of strings)
    """
    response = llm.invoke(prompt)
    import json, re
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    design = json.loads(match.group()) if match else {}
    print(f"[Infra] Design (iteration {iteration}): {design}")
    return {
        "infra_design": design,
        "infra_iteration": iteration + 1
    }


def cost_agent(state: AgentState) -> dict:
    """Estimate costs and check against budget."""
    prompt = f"""
    You are a cloud cost analyst. Estimate monthly costs for:
    {state['infra_design']}

    For an app with {state['project_spec']} requirements.

    Return JSON with keys:
    compute_usd, database_usd, cache_usd, vector_db_usd,
    llm_tokens_usd, external_api_usd, total_monthly_usd,
    cost_breakdown (list of line items)
    """
    response = llm.invoke(prompt)
    import json, re
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    estimate = json.loads(match.group()) if match else {}

    budget = state["project_spec"].get("budget_usd_per_month", 1000)
    total  = estimate.get("total_monthly_usd", 0)
    within = total <= budget

    print(f"[Cost] Total: ${total}/mo | Budget: ${budget}/mo | OK: {within}")
    return {
        "cost_estimate": estimate,
        "within_budget": within
    }


def deploy_agent(state: AgentState) -> dict:
    """Generate Terraform and Docker Compose configs."""
    prompt = f"""
    You are a DevOps engineer. Generate deployment configs for:
    {state['infra_design']}

    Return JSON with keys:
    terraform_snippet (HCL string),
    docker_compose_snippet (YAML string),
    ecs_task_definition (JSON string)
    """
    response = llm.invoke(prompt)
    import json, re
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    configs = json.loads(match.group()) if match else {}
    print("[Deploy] Configs generated.")
    return {"deployment_configs": configs}


def monitoring_agent(state: AgentState) -> dict:
    """
    In production: pull from Prometheus / OpenTelemetry.
    Here: simulate realistic metrics.
    """
    import random
    metrics = {
        "cpu_percent":          round(random.uniform(40, 95), 1),
        "memory_percent":       round(random.uniform(30, 85), 1),
        "request_latency_ms":   round(random.uniform(800, 3500), 0),
        "error_rate_percent":   round(random.uniform(0, 5), 2),
        "throughput_rps":       round(random.uniform(50, 500), 0),

        # LLM token tracking (independent budget)
        "llm_prompt_tokens_per_req":      random.randint(500, 3000),
        "llm_completion_tokens_per_req":  random.randint(100, 800),
        "llm_cost_per_request_usd":       round(random.uniform(0.01, 0.15), 4),
        "llm_burn_rate_per_min":          round(random.uniform(0.5, 5.0), 3),
        "llm_projected_monthly_usd":      round(random.uniform(200, 900), 2),

        # API token tracking (independent budget)
        "api_calls_per_min":              round(random.uniform(10, 200), 0),
        "api_cost_per_request_usd":       round(random.uniform(0.001, 0.05), 4),
        "api_burn_rate_per_min":          round(random.uniform(0.1, 2.0), 3),
        "api_quota_usage_percent":        round(random.uniform(10, 90), 1),
    }
    print(f"[Monitor] Metrics collected: CPU {metrics['cpu_percent']}%")
    return {"metrics": metrics}


def optimization_agent(state: AgentState) -> dict:
    """Analyse metrics and surface actionable recommendations."""
    prompt = f"""
    You are a FinOps and performance engineer.

    Current metrics: {state['metrics']}
    Current infrastructure: {state['infra_design']}
    Cost estimate: {state['cost_estimate']}

    Identify bottlenecks and cost anomalies. Return JSON:
    {{
      "recommendations": [
        {{
          "issue": "...",
          "action": "...",
          "projected_savings_usd_per_month": ...,
          "priority": "high|medium|low"
        }}
      ]
    }}
    """
    response = llm.invoke(prompt)
    import json, re
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    result = json.loads(match.group()) if match else {"recommendations": []}
    recs = result.get("recommendations", [])
    print(f"[Optimize] {len(recs)} recommendation(s) generated.")
    return {"recommendations": recs}


# ============================================================
# 3. CONDITIONAL EDGE
#    Called after the Cost Agent. Returns the name of the
#    NEXT NODE to visit — either "deploy" or back to "infra".
# ============================================================

MAX_INFRA_ITERATIONS = 3   # safety valve — prevent infinite loops

def route_after_cost(state: AgentState) -> str:
    iteration = state.get("infra_iteration", 0)

    if state.get("within_budget"):
        print("[Router] Budget OK → proceeding to deploy.")
        return "user_approval"             # happy path

    if iteration >= MAX_INFRA_ITERATIONS:
        print("[Router] Max iterations reached → proceeding anyway.")
        return "user_approval"             # give up gracefully

    print(f"[Router] Over budget (iteration {iteration}) → re-designing infra.")
    return "infra"                         # feedback loop


# ============================================================
# 4. HUMAN-IN-THE-LOOP NODE
#    LangGraph's interrupt() pauses execution here and waits
#    for external input (e.g. a UI button click).
# ============================================================

from langgraph.types import interrupt

def user_approval_node(state: AgentState) -> dict:
    """Pause and surface the plan for human review."""
    decision = interrupt({
        "message":       "Review the infrastructure plan and cost estimate.",
        "infra_design":  state["infra_design"],
        "cost_estimate": state["cost_estimate"],
    })
    # decision["approved"] is set by the UI / API caller via .update()
    if not decision.get("approved", True):
        raise ValueError("User rejected the plan.")
    print("[Approval] User approved → deploying.")
    return {}


# ============================================================
# 5. BUILD THE GRAPH
# ============================================================

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # --- register nodes ---
    graph.add_node("planner",       planner_agent)
    graph.add_node("infra",         infrastructure_agent)
    graph.add_node("cost",          cost_agent)
    graph.add_node("user_approval", user_approval_node)
    graph.add_node("deploy",        deploy_agent)
    graph.add_node("monitor",       monitoring_agent)
    graph.add_node("optimize",      optimization_agent)

    # --- entry point ---
    graph.set_entry_point("planner")

    # --- normal edges (always transition) ---
    graph.add_edge("planner",       "infra")
    graph.add_edge("infra",         "cost")
    graph.add_edge("user_approval", "deploy")
    graph.add_edge("deploy",        "monitor")
    graph.add_edge("monitor",       "optimize")
    graph.add_edge("optimize",      END)

    # --- conditional edge (the feedback loop) ---
    graph.add_conditional_edges(
        "cost",              # source node
        route_after_cost,    # routing function — returns node name
        {
            "user_approval": "user_approval",   # within budget
            "infra":         "infra",            # over budget → loop back
        }
    )

    return graph.compile()


# ============================================================
# 6. RUN IT
# ============================================================

if __name__ == "__main__":
    app = build_graph()

    initial_state: AgentState = {
        "user_input": (
            "We're building a RAG pipeline for 10,000 daily users "
            "with sub-2s latency and a $1000/month budget."
        ),
        "project_spec":       None,
        "infra_design":       None,
        "infra_iteration":    0,
        "cost_estimate":      None,
        "within_budget":      None,
        "deployment_configs": None,
        "metrics":            None,
        "recommendations":    None,
    }

    # stream=True prints each node's output as it completes
    for step in app.stream(initial_state, stream_mode="updates"):
        node_name = list(step.keys())[0]
        print(f"\n{'='*50}")
        print(f"Completed node: {node_name}")
        print(f"{'='*50}")

    final = app.invoke(initial_state)
    print("\n[FINAL] Recommendations:")
    for r in (final.get("recommendations") or []):
        print(f"  [{r['priority'].upper()}] {r['action']} "
              f"(saves ~${r['projected_savings_usd_per_month']}/mo)")