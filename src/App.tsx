import { useEffect, useMemo, useState } from "react";
import architectureUrl from "../docs/architecture.svg";
import { buildActivationPlan, type ActivationPlan } from "./lib/activation";
import { fetchMarketplace } from "./lib/api";
import { categoryDefinitions } from "./lib/categories";
import { bscScanTokenUrl, bscScanTransactionUrl, verifyRegistryProof } from "./lib/onchain";
import { strongestService } from "./lib/scoring";
import type { AgentCategory, CategoryResult, RankedAgent, RegistryProof } from "./lib/types";

const categoryOrder = Object.keys(categoryDefinitions) as AgentCategory[];
const apiBase = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

type DemoCase = "safe" | "poisoned" | "live-safe" | "live-poisoned";

interface HealthRecord {
  model: string;
  googleAdk: string;
  geminiConfigured: boolean;
  store: string;
  queue: string;
  runtime: string;
}

interface MissionEvent {
  sequence: number;
  stage: string;
  status: "queued" | "running" | "completed" | "blocked" | "failed";
  title: string;
  detail: string;
  at: string;
}

interface MissionVerdict {
  action: "allow_sandbox" | "human_review" | "quarantine";
  confidence: number;
  executive_summary: string;
  rationale: string[];
  required_controls: string[];
  evidence_ids: string[];
  receipt_sha256: string;
  engine: "gemini_adk" | "deterministic_demo";
}

interface MissionRecord {
  mission_id: string;
  status: "queued" | "running" | "completed" | "failed";
  target_url: string;
  events: MissionEvent[];
  verdict: MissionVerdict | null;
  error: string | null;
  previous_mission_id: string | null;
  next_review_at: string | null;
  runtime: { model?: string; framework?: string; store?: string };
}

const tierLabels: Record<RankedAgent["evidenceTier"], string> = {
  operational: "Operational evidence",
  reachable: "Reachable service metadata",
  registered: "Onchain identity",
  "metadata-only": "Metadata only",
};

function shortAddress(address: string): string {
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "not reported";
  const elapsed = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(0, Math.round(elapsed / 60_000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function EvidencePill({ label, state }: { label: string; state: "good" | "warn" | "bad" | "plain" }) {
  return <span className={`evidence-pill evidence-${state}`}>{label}</span>;
}

function AgentCard({
  agent,
  onSelect,
}: {
  agent: RankedAgent;
  onSelect: (agent: RankedAgent) => void;
}) {
  const service = strongestService(agent.services);
  const endpointState = service?.status === "healthy" ? "good" : service?.status === "degraded" ? "warn" : "bad";

  return (
    <article className="agent-card">
      <div className="agent-card-top">
        <div>
          <p className="eyebrow">ERC-8004 #{agent.tokenId}</p>
          <h3>{agent.name}</h3>
        </div>
        <div className={`score score-${agent.evidenceTier}`} aria-label={`Evidence score ${agent.evidenceScore}`}>
          {agent.evidenceScore}
        </div>
      </div>

      <p className="agent-description">{agent.description || "No description published."}</p>

      <div className="evidence-row" aria-label="Evidence summary">
        <EvidencePill label="BSC registry" state="good" />
        <EvidencePill
          label={agent.supportedProtocols.length ? agent.supportedProtocols.join(" + ") : "No protocol"}
          state={agent.supportedProtocols.length ? "plain" : "bad"}
        />
        <EvidencePill
          label={service ? `AgentCard ${service.status}` : "No service metadata"}
          state={endpointState}
        />
        {agent.x402Supported && <EvidencePill label="x402" state="plain" />}
      </div>

      <dl className="agent-metrics">
        <div>
          <dt>Evidence tier</dt>
          <dd>{tierLabels[agent.evidenceTier]}</dd>
        </div>
        <div>
          <dt>Metadata</dt>
          <dd>{Math.round(agent.metadataCompleteness)}%</dd>
        </div>
        <div>
          <dt>Health checked</dt>
          <dd>{timeAgo(service?.checkedAt ?? null)}</dd>
        </div>
        <div>
          <dt>Feedbacks</dt>
          <dd>{agent.totalFeedbacks}</dd>
        </div>
      </dl>

      <button className="primary-button" onClick={() => onSelect(agent)}>
        Inspect receipts
        <span aria-hidden="true">↗</span>
      </button>
    </article>
  );
}

function CategorySection({ result, onSelect }: { result: CategoryResult; onSelect: (agent: RankedAgent) => void }) {
  return (
    <section className="category-section" id={result.category.id} style={{ "--accent": result.category.accent } as React.CSSProperties}>
      <header className="category-header">
        <div className="category-number">{String(categoryOrder.indexOf(result.category.id) + 1).padStart(2, "0")}</div>
        <div>
          <p className="eyebrow">Equal-depth category</p>
          <h2>{result.category.label}</h2>
          <p>{result.category.description}</p>
        </div>
        <div className="source-stamp">
          <span className="live-dot" /> Live 8004scan
          <small>{timeAgo(result.fetchedAt)}</small>
        </div>
      </header>

      {result.warning && <p className="inline-warning">{result.warning}</p>}
      <div className="agent-grid">
        {result.agents.slice(0, 3).map((agent) => (
          <AgentCard key={`${agent.category}-${agent.tokenId}`} agent={agent} onSelect={onSelect} />
        ))}
        {result.agents.length === 0 && (
          <div className="empty-card">No candidate passed the category-relevance gate.</div>
        )}
      </div>
    </section>
  );
}

function Inspector({ agent, onClose }: { agent: RankedAgent; onClose: () => void }) {
  const [proof, setProof] = useState<RegistryProof | null>(null);
  const [proofError, setProofError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [objective, setObjective] = useState("Compare this agent's read-only recommendation with current onchain data.");
  const [plan, setPlan] = useState<ActivationPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const service = strongestService(agent.services);

  useEffect(() => {
    setProof(null);
    setProofError(null);
    setPlan(null);
    setPlanError(null);
  }, [agent.tokenId]);

  async function verify() {
    setVerifying(true);
    setProofError(null);
    try {
      setProof(await verifyRegistryProof(agent));
    } catch (error) {
      setProofError(error instanceof Error ? error.message : "Registry verification failed");
    } finally {
      setVerifying(false);
    }
  }

  function generatePlan() {
    setPlanError(null);
    try {
      setPlan(buildActivationPlan(agent, objective, proof));
    } catch (error) {
      setPlan(null);
      setPlanError(error instanceof Error ? error.message : "Activation plan could not be created");
    }
  }

  return (
    <div className="inspector-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="inspector" role="dialog" aria-modal="true" aria-label={`Evidence for ${agent.name}`}>
        <header className="inspector-header">
          <div>
            <p className="eyebrow">Evidence, not endorsements</p>
            <h2>{agent.name}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close inspector">×</button>
        </header>

        <div className="receipt-block">
          <div className="receipt-heading">
            <span>01</span>
            <div><strong>Identity receipt</strong><small>Direct BSC read, not API trust</small></div>
          </div>
          <dl className="receipt-list">
            <div><dt>Registry</dt><dd>{shortAddress(agent.contractAddress)}</dd></div>
            <div><dt>Token</dt><dd>#{agent.tokenId}</dd></div>
            <div><dt>Indexed owner</dt><dd>{shortAddress(agent.ownerAddress)}</dd></div>
            {proof && <div><dt>Block</dt><dd>{proof.blockNumber.toString()}</dd></div>}
          </dl>
          <div className="button-row">
            <button className="secondary-button" onClick={verify} disabled={verifying}>
              {verifying ? "Checking BSC…" : proof ? "Verify again" : "Verify on BSC"}
            </button>
            <a className="text-link" href={bscScanTokenUrl(agent)} target="_blank" rel="noreferrer">BscScan ↗</a>
          </div>
          {proof && (
            <p className={proof.verified ? "status-good" : "status-bad"}>
              {proof.verified ? "Owner matches the live registry." : "Owner mismatch. Activation remains blocked."}
            </p>
          )}
          {proofError && <p className="status-bad">{proofError}</p>}
        </div>

        <div className="receipt-block">
          <div className="receipt-heading">
            <span>02</span>
            <div><strong>Service receipt</strong><small>Discovery health is not execution health</small></div>
          </div>
          <dl className="receipt-list">
            <div><dt>Protocol</dt><dd>{agent.supportedProtocols.join(", ") || "None"}</dd></div>
            <div><dt>Discovery URL</dt><dd>{service?.endpoint ? new URL(service.endpoint).hostname : "Not published"}</dd></div>
            <div><dt>Domain proof</dt><dd>{service?.domainVerified ? "verified" : "not verified"}</dd></div>
            <div><dt>Execution target</dt><dd>{service?.executionTargetVerified ? "bounded check passed" : "not validated"}</dd></div>
            <div><dt>Status</dt><dd>{service?.status ?? "unknown"}</dd></div>
            <div><dt>Last check</dt><dd>{timeAgo(service?.checkedAt ?? null)}</dd></div>
          </dl>
          {service?.message && <p className="service-message">{service.message}</p>}
          {agent.createdTxHash && (
            <a className="text-link" href={bscScanTransactionUrl(agent.createdTxHash)} target="_blank" rel="noreferrer">
              Registration transaction ↗
            </a>
          )}
        </div>

        <div className="receipt-block">
          <div className="receipt-heading">
            <span>03</span>
            <div><strong>Bounded activation</strong><small>No custody, trade, or message is sent here</small></div>
          </div>
          <label className="field-label" htmlFor="objective">Read-only objective</label>
          <textarea id="objective" value={objective} maxLength={500} onChange={(event) => setObjective(event.target.value)} />
          <button
            className="primary-button"
            onClick={generatePlan}
            disabled={agent.activationBlockedReasons.length > 0 || !proof?.verified}
          >
            Generate activation plan
          </button>
          {agent.activationBlockedReasons.length > 0 && (
            <div className="blocked-box">
              <strong>Activation blocked</strong>
              <ul>{agent.activationBlockedReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
            </div>
          )}
          {agent.activationBlockedReasons.length === 0 && !proof?.verified && (
            <p className="status-bad">Verify the live BSC owner before generating a plan.</p>
          )}
          {planError && <p className="status-bad">{planError}</p>}
          {plan && <pre className="plan-preview">{JSON.stringify(plan, null, 2)}</pre>}
        </div>
      </aside>
    </div>
  );
}

function MissionLab() {
  const [demoCase, setDemoCase] = useState<DemoCase>("poisoned");
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [health, setHealth] = useState<HealthRecord | null>(null);
  const [running, setRunning] = useState(false);
  const [missionError, setMissionError] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiBase}/healthz`)
      .then((response) => response.ok ? response.json() as Promise<HealthRecord> : Promise.reject(new Error("health unavailable")))
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!mission || !["queued", "running"].includes(mission.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`${apiBase}/api/missions/${mission.mission_id}`);
      if (!response.ok) return;
      const next = await response.json() as MissionRecord;
      setMission(next);
      if (["completed", "failed"].includes(next.status)) setRunning(false);
    }, 650);
    return () => window.clearInterval(timer);
  }, [mission?.mission_id, mission?.status]);

  async function runMission() {
    setMission(null);
    setMissionError(null);
    setRunning(true);
    try {
      const response = await fetch(`${apiBase}/api/missions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: demoCase.startsWith("live-")
            ? `${window.location.origin}/agentcards/${demoCase.replace("live-", "")}.json`
            : `https://demo.fourproof.invalid/${demoCase}`,
          ...(demoCase.startsWith("live-") ? {} : { demo_case: demoCase }),
          objective: "Decide whether this external agent may enter an isolated enterprise sandbox.",
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({})) as { detail?: string };
        throw new Error(detail.detail ?? `Mission API returned ${response.status}`);
      }
      setMission(await response.json() as MissionRecord);
    } catch (error) {
      setMissionError(error instanceof Error ? error.message : "Mission could not start");
      setRunning(false);
    }
  }

  const verdictClass = mission?.verdict?.action === "quarantine"
    ? "verdict-quarantine"
    : mission?.verdict?.action === "allow_sandbox"
      ? "verdict-allow"
      : "verdict-review";

  return (
    <section className="mission-section" id="mission">
      <div className="mission-intro">
        <p className="eyebrow">Live mission control</p>
        <h2>Trust an agent only after the fleet tries to disprove it.</h2>
        <p>
          Three independent reviewers inspect discovery, identity, and tool safety in parallel. A final policy judge can
          quarantine the agent, request human review, or allow only an isolated sandbox.
        </p>
        <div className="demo-selector" role="group" aria-label="Choose a reproducible inspection target">
          <button className={demoCase === "poisoned" ? "active" : ""} onClick={() => setDemoCase("poisoned")}>Poisoned card</button>
          <button className={demoCase === "safe" ? "active" : ""} onClick={() => setDemoCase("safe")}>Incomplete safe card</button>
          <button className={demoCase === "live-poisoned" ? "active" : ""} onClick={() => setDemoCase("live-poisoned")}>Live poisoned</button>
          <button className={demoCase === "live-safe" ? "active" : ""} onClick={() => setDemoCase("live-safe")}>Live safe</button>
        </div>
        <button className="primary-button mission-run" onClick={() => void runMission()} disabled={running}>
          {running ? "Fleet reviewing…" : "Launch evidence mission"}<span>→</span>
        </button>
        <p className="runtime-disclosure">
          Embedded cases are deterministic and labeled. “Live” cases fetch deployed public cards and require authenticated Gemini 3.5 Flash through Google ADK.
        </p>
        {health && (
          <dl className="runtime-grid" aria-label="Observed backend configuration">
            <div><dt>runtime</dt><dd>{health.runtime}</dd></div>
            <div><dt>store</dt><dd>{health.store}</dd></div>
            <div><dt>queue</dt><dd>{health.queue}</dd></div>
            <div><dt>gemini</dt><dd>{health.geminiConfigured ? "configured" : "not configured"}</dd></div>
          </dl>
        )}
      </div>

      <div className="mission-console" aria-live="polite">
        <div className="console-topline">
          <span className="live-dot" />
          <strong>{mission ? `Mission ${mission.mission_id.slice(0, 8)}` : "Awaiting mission"}</strong>
          <small>{mission?.runtime.model ?? "no model invoked"}</small>
        </div>
        {!mission && !missionError && (
          <div className="console-empty">
            <span>4P</span>
            <p>Select a target and launch the autonomous review.</p>
          </div>
        )}
        {missionError && <p className="status-bad">{missionError}</p>}
        {mission && (
          <ol className="event-timeline">
            {mission.events.map((event) => (
              <li key={`${event.sequence}-${event.at}`} className={`event-${event.status}`}>
                <span>{String(event.sequence).padStart(2, "0")}</span>
                <div><strong>{event.title}</strong><p>{event.detail}</p></div>
              </li>
            ))}
          </ol>
        )}
        {mission?.verdict && (
          <div className={`verdict-card ${verdictClass}`}>
            <div><span>Policy decision</span><strong>{mission.verdict.action.replace("_", " ")}</strong></div>
            <b>{Math.round(mission.verdict.confidence * 100)}%</b>
            <p>{mission.verdict.executive_summary}</p>
            <small>
              Receipt {mission.verdict.receipt_sha256.slice(0, 20)}… · {mission.verdict.engine}
              {mission.next_review_at ? ` · review ${new Date(mission.next_review_at).toLocaleDateString()}` : ""}
            </small>
          </div>
        )}
      </div>
    </section>
  );
}

export default function App() {
  const [results, setResults] = useState<CategoryResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<RankedAgent | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setResults(await fetchMarketplace());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load the marketplace");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const stats = useMemo(() => {
    const agents = results.flatMap((result) => result.agents);
    return {
      categories: results.length,
      candidates: agents.length,
      operational: agents.filter((agent) => agent.evidenceTier === "operational").length,
      blocked: agents.filter((agent) => agent.activationBlockedReasons.length > 0).length,
    };
  }, [results]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="FourProof Fleet home">
          <span className="brand-mark">4P</span>
          <span>FourProof Fleet</span>
        </a>
        <nav aria-label="Product sections">
          <a href="#mission">Mission control</a>
          <a href="#registry">Live registry</a>
          <a href="#architecture">Architecture</a>
        </nav>
        <button className="refresh-button" onClick={() => void load()} disabled={loading}>
          {loading ? "Syncing…" : "Refresh evidence"}
        </button>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Zero-trust agent onboarding · Google ADK</p>
            <h1>Hire the agent.<br />Not the risk.</h1>
            <p className="hero-lede">
              An autonomous review fleet intercepts third-party agents before production—proving identity, detecting tool poisoning, and sealing every decision to an evidence receipt.
            </p>
            <div className="hero-actions">
              <a className="primary-button" href="#mission">Run the red-team demo</a>
              <a className="text-link" href="#architecture">See the evidence flow ↓</a>
            </div>
          </div>
          <div className="hero-scorecard" aria-label="Fleet architecture summary">
            <p className="eyebrow">Production-minded by default</p>
            <div className="scorecard-grid">
              <div><strong>3+1</strong><span>specialists + judge</span></div>
              <div><strong>3.5</strong><span>Gemini Flash model</span></div>
              <div><strong>256K</strong><span>bounded card bytes</span></div>
              <div><strong>0</strong><span>secrets sent to targets</span></div>
            </div>
            <p className="truth-note"><span /> Untrusted AgentCard text stays data—never system instruction.</p>
          </div>
        </section>

        <section className="method-strip" aria-label="How the fleet reviews external agents">
          <div><span>01</span><strong>Scout</strong><small>Capture claims and immutable bytes</small></div>
          <div><span>02</span><strong>Verify</strong><small>Separate identity claims from proof</small></div>
          <div><span>03</span><strong>Guard</strong><small>Detect injection and unsafe targets</small></div>
          <div><span>04</span><strong>Judge</strong><small>Quarantine, review, or sandbox</small></div>
        </section>

        <MissionLab />

        {error && (
          <section className="error-panel">
            <strong>Live discovery unavailable</strong>
            <p>{error}</p>
            <button className="secondary-button" onClick={() => void load()}>Try again</button>
          </section>
        )}

        {loading && results.length === 0 && (
          <section className="loading-panel">
            <div className="loading-line" />
            <p>Reading BSC identities and service-discovery evidence…</p>
          </section>
        )}

        <div className="categories-wrap" id="registry">
          <header className="registry-intro">
            <p className="eyebrow">Live agent registry</p>
            <h2>The fleet starts from evidence already in the world.</h2>
            <p>{stats.candidates} live BSC identities are currently ranked across {stats.categories}/4 discovery categories; {stats.blocked} remain blocked by missing evidence.</p>
          </header>
          {categoryOrder.map((category) => {
            const result = results.find((item) => item.category.id === category);
            return result ? <CategorySection key={category} result={result} onSelect={setSelected} /> : null;
          })}
        </div>

        <section className="disclosure" id="architecture">
          <p className="eyebrow">Cloud architecture</p>
          <h2>Cloud Run executes. Firestore remembers. Pub/Sub retries. Receipts explain.</h2>
          <figure className="architecture-figure">
            <img src={architectureUrl} alt="FourProof Fleet zero-trust Google Cloud architecture" />
            <figcaption>One bounded gateway, three independent reviewers, one fail-closed judge.</figcaption>
          </figure>
          <p>
            Google ADK runs Registry Scout, Identity Verifier, and Tool Guard concurrently on Gemini 3.5 Flash, then routes their independent reports to a fail-closed Policy Judge. Every mission is persisted as an event stream; production secrets and private network targets never cross the gateway.
          </p>
        </section>
      </main>

      <footer>
        <span>FourProof Fleet · Gemini 3.5 Flash · Google ADK</span>
        <span>Fortified Enterprise Fleet · explicit evidence, not endorsements</span>
      </footer>

      {selected && <Inspector agent={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
