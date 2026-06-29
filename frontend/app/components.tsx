"use client";

import { useState } from "react";
import type {
  Cost,
  Infrastructure,
  Monitoring,
  Optimization,
  Requirements,
  TimePoint,
} from "@/lib/api";

const money = (n: number) =>
  n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const STEPS = [
  "Requirements",
  "Plan",
  "Infrastructure",
  "Cost",
  "Approve",
  "Monitor & Optimize",
];

export function Stepper({ current }: { current: number }) {
  return (
    <div className="stepper">
      {STEPS.map((label, i) => {
        const state = i < current ? "done" : i === current ? "active" : "";
        return (
          <div key={label} className={`step-pill ${state}`}>
            <span className="dot">{i < current ? "✓" : i + 1}</span>
            {label}
          </div>
        );
      })}
    </div>
  );
}

export function RequirementsCard({ req }: { req: Requirements }) {
  return (
    <div className="card fade-in">
      <span className="agent-tag">PLANNER AGENT</span>
      <h2>Structured Requirements</h2>
      <p className="muted">{req.summary}</p>
      <div className="grid">
        <Kv k="Application" v={req.application_type} />
        <Kv k="Users / day" v={req.users_per_day.toLocaleString()} />
        <Kv k="Latency target" v={`${req.latency_requirement_seconds}s`} />
        <Kv k="Budget" v={`${money(req.budget_usd_monthly)}/mo`} />
        <Kv k="Documents" v={req.document_count.toLocaleString()} />
        <Kv k="LLM provider" v={req.preferred_llm_provider} />
      </div>
      {req.constraints?.length > 0 && (
        <>
          <h3>Constraints</h3>
          <div className="row">
            {req.constraints.map((c) => (
              <span key={c} className="pill cat">
                {c}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function InfrastructureCard({ infra }: { infra: Infrastructure }) {
  return (
    <div className="card fade-in">
      <span className="agent-tag">INFRASTRUCTURE AGENT</span>
      <h2>
        Architecture <span className="pill cat">{infra.tier}</span>
      </h2>
      <p className="muted">{infra.notes}</p>
      <div className="grid">
        {Object.entries(infra.components).map(([k, v]) => (
          <Kv key={k} k={k.replace(/_/g, " ")} v={v} small />
        ))}
      </div>
      <h3>Scaling strategy</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        {infra.scaling_strategy}
      </p>
      <h3>Trade-offs</h3>
      <table>
        <thead>
          <tr>
            <th>Decision</th>
            <th>Chosen</th>
            <th>Alternative</th>
            <th>Rationale</th>
          </tr>
        </thead>
        <tbody>
          {infra.tradeoffs.map((t, i) => (
            <tr key={i}>
              <td>{t.decision}</td>
              <td>{t.chosen}</td>
              <td className="muted">{t.alternative}</td>
              <td className="muted">{t.rationale}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CostCard({ cost, redesigns }: { cost: Cost; redesigns: number }) {
  return (
    <div className="card fade-in">
      <span className="agent-tag">COST AGENT</span>
      <h2 className="row spread">
        <span>Cost Estimate</span>
        <span className={`pill ${cost.within_budget ? "ok" : "bad"}`}>
          {cost.within_budget ? "Within budget" : "Over budget"}
        </span>
      </h2>
      <p className="muted">{cost.notes}</p>
      {redesigns > 0 && (
        <p className="muted">
          🔁 Infrastructure was redesigned {redesigns}{" "}
          {redesigns === 1 ? "time" : "times"} to meet the budget.
        </p>
      )}
      <div className="grid">
        <Kv k="Infra" v={money(cost.infra_total_usd)} />
        <Kv k="LLM tokens" v={money(cost.llm_total_usd)} />
        <Kv k="External API" v={money(cost.external_api_total_usd)} />
        <Kv k="Total / month" v={money(cost.total_monthly_usd)} />
        <Kv k="Budget" v={money(cost.budget_usd)} />
      </div>
      <h3>Breakdown</h3>
      <table>
        <thead>
          <tr>
            <th>Category</th>
            <th>Item</th>
            <th className="num">Monthly</th>
          </tr>
        </thead>
        <tbody>
          {cost.breakdown.map((b, i) => (
            <tr key={i}>
              <td>
                <span className="pill cat">{b.category}</span>
              </td>
              <td>{b.item}</td>
              <td className="num">{money(b.monthly_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sparkline({ points, field }: { points: TimePoint[]; field: keyof TimePoint }) {
  const vals = points.map((p) => Number(p[field]));
  const max = Math.max(...vals, 1);
  return (
    <div className="spark">
      {vals.map((v, i) => (
        <div key={i} className="bar" style={{ height: `${(v / max) * 100}%` }} title={`${v}`} />
      ))}
    </div>
  );
}

export function MonitoringCard({ mon }: { mon: Monitoring }) {
  const app = mon.application_metrics;
  const infra = mon.infrastructure_metrics;
  const llm = mon.llm_tokens;
  return (
    <div className="card fade-in">
      <span className="agent-tag">MONITORING AGENT</span>
      <h2>Live Metrics (simulated)</h2>

      {mon.alerts.length > 0 && (
        <>
          <h3>Alerts</h3>
          {mon.alerts.map((a, i) => (
            <div key={i} className={`alert ${a.severity}`}>
              <strong>{a.severity.toUpperCase()}</strong> · {a.message}
            </div>
          ))}
        </>
      )}

      <h3>Application</h3>
      <div className="grid">
        <Kv k="Avg latency" v={`${app.avg_latency_ms} ms`} />
        <Kv k="Peak latency" v={`${app.peak_latency_ms} ms`} />
        <Kv k="Error rate" v={`${app.error_rate_pct}%`} />
        <Kv k="Throughput" v={`${app.throughput_rps} rps`} />
      </div>

      <h3>Infrastructure</h3>
      <div className="grid">
        <Kv k="CPU" v={`${infra.cpu_pct}%`} />
        <Kv k="Memory" v={`${infra.memory_pct}%`} />
        <Kv k="Disk" v={`${infra.disk_pct}%`} />
        <Kv k="Network" v={`${infra.network_mbps} Mbps`} />
      </div>

      <h3>Token budgets (LLM vs External API — tracked independently)</h3>
      <div className="grid">
        <Kv k="LLM burn" v={`${Math.round(llm.burn_rate_tokens_per_min).toLocaleString()} tok/min`} />
        <Kv k="LLM peak" v={`${Math.round(llm.peak_burn_tokens_per_min).toLocaleString()} tok/min`} />
        <Kv k="LLM monthly" v={money(llm.monthly_cost_usd)} />
        <Kv k="API monthly" v={money(mon.api_tokens.monthly_cost_usd)} />
        <Kv k="API quota" v={`${mon.api_tokens.quota_usage_pct}%`} />
        <Kv
          k="Projected overrun"
          v={mon.projected_monthly_overrun_usd > 0 ? money(mon.projected_monthly_overrun_usd) : "None"}
        />
      </div>

      <h3>Request latency (last {mon.timeseries.length} min)</h3>
      <Sparkline points={mon.timeseries} field="latency_ms" />
      <h3>LLM token burn rate</h3>
      <Sparkline points={mon.timeseries} field="llm_tokens_per_min" />
    </div>
  );
}

export function OptimizationCard({ opt }: { opt: Optimization }) {
  return (
    <div className="card fade-in">
      <span className="agent-tag">OPTIMIZATION AGENT</span>
      <h2 className="row spread">
        <span>Recommendations</span>
        <span className="pill ok">
          Save ~{money(opt.total_projected_savings_usd_monthly)}/mo
        </span>
      </h2>
      <p className="muted">{opt.summary}</p>
      <table>
        <thead>
          <tr>
            <th>Recommendation</th>
            <th>Category</th>
            <th>Effort</th>
            <th className="num">Savings/mo</th>
            <th className="num">%</th>
          </tr>
        </thead>
        <tbody>
          {opt.recommendations.map((r, i) => (
            <tr key={i}>
              <td>
                <strong>{r.title}</strong>
                <div className="muted">{r.rationale}</div>
              </td>
              <td>
                <span className="pill cat">{r.category}</span>
              </td>
              <td>
                <span className={`pill ${r.effort === "low" ? "ok" : "warn"}`}>{r.effort}</span>
              </td>
              <td className="num">{money(r.projected_savings_usd_monthly)}</td>
              <td className="num">{r.projected_savings_pct}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ARTIFACT_LABELS: Record<string, string> = {
  docker_compose: "docker-compose.yml",
  dockerfile_backend: "Dockerfile",
  terraform: "main.tf",
  k8s_manifest: "k8s.yaml",
};

export function DeploymentCard({ artifacts, notes }: { artifacts: Record<string, string>; notes: string }) {
  const keys = Object.keys(artifacts);
  const [active, setActive] = useState(keys[0]);
  return (
    <div className="card fade-in">
      <span className="agent-tag">DEPLOY AGENT</span>
      <h2>Deployment Artifacts</h2>
      <p className="muted">{notes}</p>
      <div className="tabs">
        {keys.map((k) => (
          <button
            key={k}
            className={`tab ${k === active ? "active" : ""}`}
            onClick={() => setActive(k)}
          >
            {ARTIFACT_LABELS[k] || k}
          </button>
        ))}
      </div>
      <pre>{artifacts[active]}</pre>
    </div>
  );
}

function Kv({ k, v, small }: { k: string; v: string; small?: boolean }) {
  return (
    <div className="kv">
      <div className="k">{k}</div>
      <div className="v" style={small ? { fontSize: 14 } : undefined}>
        {v}
      </div>
    </div>
  );
}
