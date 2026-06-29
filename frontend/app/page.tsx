"use client";

import { useEffect, useState } from "react";
import { approveSession, createSession, getHealth, type SessionResponse } from "@/lib/api";
import {
  CostCard,
  DeploymentCard,
  InfrastructureCard,
  MonitoringCard,
  OptimizationCard,
  RequirementsCard,
  Stepper,
} from "./components";

const EXAMPLE =
  "We're building a RAG chatbot for 10,000 daily users with sub-2s latency, " +
  "storing 1 million documents, budget under $1000/month using OpenAI models.";

export default function Home() {
  const [input, setInput] = useState(EXAMPLE);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [planning, setPlanning] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockMode, setMockMode] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setMockMode(h.mock_llm))
      .catch(() => setMockMode(null));
  }, []);

  // Derive the stepper position from the session state.
  let current = 0;
  if (session?.status === "deployed") current = 5;
  else if (session?.status === "planned") current = 4; // awaiting approval

  async function onPlan() {
    setError(null);
    setPlanning(true);
    setSession(null);
    try {
      setSession(await createSession(input));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to run the plan.");
    } finally {
      setPlanning(false);
    }
  }

  async function onApprove() {
    if (!session) return;
    setError(null);
    setDeploying(true);
    try {
      setSession(await approveSession(session.session_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to deploy.");
    } finally {
      setDeploying(false);
    }
  }

  function reset() {
    setSession(null);
    setError(null);
  }

  return (
    <main className="container">
      <div className="header row spread">
        <div>
          <h1>Agent Infrastructure SaaS</h1>
          <p>Describe your app → design, cost, deploy, monitor & optimize — by a 6-agent pipeline.</p>
        </div>
        {mockMode !== null && (
          <span className={`badge ${mockMode ? "mock" : "live"}`}>
            {mockMode ? "MOCK LLM" : "LIVE OpenAI"}
          </span>
        )}
      </div>

      <Stepper current={current} />

      {error && <div className="error-box">⚠️ {error}</div>}

      {/* Step 1: requirements input */}
      {!session && (
        <div className="card">
          <span className="agent-tag">INPUT</span>
          <h2>Describe your application</h2>
          <p className="muted">Natural language — the Planner Agent will structure it.</p>
          <textarea value={input} onChange={(e) => setInput(e.target.value)} disabled={planning} />
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn-primary" onClick={onPlan} disabled={planning || input.trim().length < 3}>
              {planning ? "Running Planner → Infra → Cost…" : "Generate Plan"}
            </button>
            <button className="btn-ghost" onClick={() => setInput(EXAMPLE)} disabled={planning}>
              Use example
            </button>
          </div>
        </div>
      )}

      {/* Plan phase outputs */}
      {session?.requirements && <RequirementsCard req={session.requirements} />}
      {session?.infrastructure && <InfrastructureCard infra={session.infrastructure} />}
      {session?.cost && <CostCard cost={session.cost} redesigns={session.redesign_count} />}

      {/* Approval gate */}
      {session?.status === "planned" && (
        <div className="card">
          <h2>Approve & Deploy</h2>
          <p className="muted">
            Review the plan above. Approving runs the Deploy, Monitoring, and Optimization agents.
          </p>
          <div className="row">
            <button className="btn-primary" onClick={onApprove} disabled={deploying}>
              {deploying ? "Running Deploy → Monitor → Optimize…" : "Approve & Deploy"}
            </button>
            <button className="btn-ghost" onClick={reset} disabled={deploying}>
              Start over
            </button>
          </div>
        </div>
      )}

      {/* Deploy phase outputs */}
      {session?.deployment && (
        <DeploymentCard artifacts={session.deployment.artifacts} notes={session.deployment.notes} />
      )}
      {session?.monitoring && <MonitoringCard mon={session.monitoring} />}
      {session?.optimization && <OptimizationCard opt={session.optimization} />}

      {session?.status === "deployed" && (
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn-ghost" onClick={reset}>
            Start a new plan
          </button>
        </div>
      )}
    </main>
  );
}
