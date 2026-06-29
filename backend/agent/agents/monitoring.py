"""Monitoring agent — simulated post-deploy metrics.

There is no real infrastructure to scrape, so this agent deterministically
simulates the signals the README calls for: infra/app metrics, independent LLM
and external-API token tracking (burn rate, per-request cost, projected
overrun), a short time series for charts, and threshold-based alerts. The
simulation is seeded from the spec so the same input always yields the same
numbers (important for reproducible tests).
"""
from __future__ import annotations

import math
import random
from typing import Any

from agent.state import GraphState

_POINTS = 20  # time-series samples (e.g. last 20 minutes)


def _simulate(spec: dict[str, Any], cost: dict[str, Any]) -> dict[str, Any]:
    users = float(spec.get("users_per_day", 10000) or 10000)
    latency_target_s = float(spec.get("latency_requirement_seconds", 2) or 2)
    budget = float(cost.get("budget_usd_monthly", cost.get("budget_usd", 1000)) or 1000)
    monthly_llm = float(cost.get("llm_total_usd", 300) or 300)
    monthly_api = float(cost.get("external_api_total_usd", 100) or 100)

    rng = random.Random(int(users) ^ int(budget) ^ 0x5EED)

    rps_avg = users / 86400.0
    # Load the box ~70-90% so metrics look like a real busy service.
    cpu = min(99, 55 + rng.uniform(0, 30))
    mem = min(99, 50 + rng.uniform(0, 25))

    series = []
    for i in range(_POINTS):
        wave = math.sin(i / 3.0)
        rps = max(0.1, rps_avg * (1 + 0.4 * wave) + rng.uniform(-0.05, 0.05) * rps_avg)
        latency_ms = (latency_target_s * 1000) * (0.7 + 0.35 * (wave + 1) / 2) + rng.uniform(-40, 40)
        llm_tokens = rps * 60 * rng.uniform(800, 1200)  # tokens/min
        series.append({
            "t": i,
            "rps": round(rps, 2),
            "latency_ms": round(max(50, latency_ms), 1),
            "cpu_pct": round(min(99, cpu + 8 * wave + rng.uniform(-3, 3)), 1),
            "llm_tokens_per_min": round(llm_tokens, 0),
        })

    avg_latency = sum(p["latency_ms"] for p in series) / len(series)
    peak_latency = max(p["latency_ms"] for p in series)
    llm_burn = sum(p["llm_tokens_per_min"] for p in series) / len(series)
    peak_burn = max(p["llm_tokens_per_min"] for p in series)

    # Per-request token cost vs rolling baseline (anomaly if a sample spikes).
    baseline_cost_per_req = monthly_llm / max(1, users * 30)
    error_rate = round(rng.uniform(0.1, 1.2), 2)

    # Projected overrun: extrapolate the observed burn against the monthly budget.
    projected_llm = monthly_llm * (1 + (peak_burn / max(1, llm_burn) - 1) * 0.3)
    projected_overrun = max(0.0, (projected_llm + monthly_api) - budget)

    alerts: list[dict[str, Any]] = []
    if peak_burn > 1.8 * llm_burn:
        alerts.append({
            "type": "burn_rate_spike",
            "token_type": "llm",
            "severity": "warning",
            "message": f"LLM token burn spiked to {peak_burn:,.0f}/min (>1.8x the {llm_burn:,.0f}/min baseline).",
        })
    if peak_latency > latency_target_s * 1000:
        alerts.append({
            "type": "latency_breach",
            "severity": "warning",
            "message": f"Peak latency {peak_latency:,.0f}ms exceeds the {latency_target_s:g}s target.",
        })
    if projected_overrun > 0:
        alerts.append({
            "type": "projected_overrun",
            "token_type": "llm",
            "severity": "critical",
            "message": f"Projected monthly spend exceeds budget by ${projected_overrun:,.0f}.",
        })

    return {
        "infrastructure_metrics": {
            "cpu_pct": round(cpu, 1),
            "memory_pct": round(mem, 1),
            "gpu_pct": 0.0,
            "network_mbps": round(rps_avg * rng.uniform(0.4, 0.8), 2),
            "disk_pct": round(rng.uniform(20, 60), 1),
        },
        "application_metrics": {
            "avg_latency_ms": round(avg_latency, 1),
            "peak_latency_ms": round(peak_latency, 1),
            "error_rate_pct": error_rate,
            "throughput_rps": round(rps_avg, 2),
        },
        "llm_tokens": {
            "prompt_tokens_per_min": round(llm_burn * 0.7, 0),
            "completion_tokens_per_min": round(llm_burn * 0.3, 0),
            "burn_rate_tokens_per_min": round(llm_burn, 0),
            "peak_burn_tokens_per_min": round(peak_burn, 0),
            "cost_per_request_usd": round(baseline_cost_per_req, 6),
            "monthly_cost_usd": round(monthly_llm, 2),
            "projected_monthly_cost_usd": round(projected_llm, 2),
        },
        "api_tokens": {
            "calls_per_min": round(llm_burn / 1000 * rng.uniform(0.8, 1.2), 1),
            "monthly_cost_usd": round(monthly_api, 2),
            "quota_usage_pct": round(rng.uniform(35, 75), 1),
            "burn_rate_calls_per_min": round(llm_burn / 900, 1),
        },
        "budget_usd": budget,
        "projected_monthly_overrun_usd": round(projected_overrun, 2),
        "timeseries": series,
        "alerts": alerts,
    }


def monitoring_node(state: GraphState) -> dict[str, Any]:
    spec = state.get("requirements", {})
    cost = state.get("cost", {})
    metrics = _simulate(spec, cost)
    return {"monitoring": metrics, "steps": [{"agent": "monitoring", "output": metrics}]}
