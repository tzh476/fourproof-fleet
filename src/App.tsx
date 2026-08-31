import { useEffect, useState } from "react";
import architectureUrl from "../docs/architecture.svg";

const apiBase = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
const verifiedProofMissionId = "aa919f3ac5eb4cf68c0aed1b51d721f8";
const verifiedProofGitSha = "6c1c35ce03138fc38b2ceaabb8188f6e31f6b59f";

type DemoCase = "safe" | "poisoned";

interface HealthRecord {
  model: string;
  googleAdk: string;
  geminiConfigured: boolean;
  store: string;
  queue: string;
  runtime: string;
  gitSha: string;
  liveMissionTotalLimit: number;
  maxLlmCallsPerMission: number;
  maxOutputTokensPerCall: number;
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
  evidence_sha256: string[];
  evidence_set_sha256: string;
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

function MissionLab() {
  const [demoCase, setDemoCase] = useState<DemoCase>("poisoned");
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [health, setHealth] = useState<HealthRecord | null>(null);
  const [running, setRunning] = useState(false);
  const [missionError, setMissionError] = useState<string | null>(null);
  const [proofStatus, setProofStatus] = useState<"loading" | "verified" | "unavailable">("loading");

  useEffect(() => {
    void fetch(`${apiBase}/health`)
      .then((response) => response.ok ? response.json() as Promise<HealthRecord> : Promise.reject(new Error("health unavailable")))
      .then((record) => {
        setHealth(record);
        if (record.store === "firestore") return loadVerifiedProof();
        setProofStatus("unavailable");
      })
      .catch(() => {
        setHealth(null);
        setProofStatus("unavailable");
      });
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

  async function loadVerifiedProof() {
    setProofStatus("loading");
    setMissionError(null);
    try {
      const response = await fetch(`${apiBase}/api/missions/${verifiedProofMissionId}`);
      if (!response.ok) throw new Error(`proof endpoint returned ${response.status}`);
      const proof = await response.json() as MissionRecord;
      if (proof.status !== "completed" || proof.verdict?.engine !== "gemini_adk") {
        throw new Error("proof mission is not a completed Gemini/ADK run");
      }
      setMission(proof);
      setProofStatus("verified");
    } catch {
      setProofStatus("unavailable");
    }
  }

  async function runMission() {
    setMission(null);
    setMissionError(null);
    setProofStatus("unavailable");
    setRunning(true);
    try {
      const response = await fetch(`${apiBase}/api/missions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: `https://demo.fourproof.invalid/${demoCase}`,
          demo_case: demoCase,
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
  const verifiedProofVisible = proofStatus === "verified" && mission?.mission_id === verifiedProofMissionId;

  return (
    <section className="mission-section" id="mission">
      <div className="mission-intro">
        <p className="eyebrow">Live mission control</p>
        <h2>Trust an agent only after the fleet tries to disprove it.</h2>
        <p>
          Three independent reviewers inspect discovery, identity, and tool safety in parallel. A final policy judge can
          quarantine the agent, request human review, or allow only an isolated sandbox.
        </p>
        <p className="runtime-disclosure">
          Built for the AI fleet librarian: an operations coordinator who needs security-grade evidence without becoming a security engineer.
        </p>
        <div className="demo-selector" role="group" aria-label="Choose a reproducible inspection target">
          <button className={demoCase === "poisoned" ? "active" : ""} onClick={() => setDemoCase("poisoned")}>Red-team fixture</button>
          <button className={demoCase === "safe" ? "active" : ""} onClick={() => setDemoCase("safe")}>Incomplete safe fixture</button>
        </div>
        <button className="primary-button mission-run" onClick={() => void runMission()} disabled={running}>
          {running ? "Fleet reviewing…" : "Launch deterministic review"}<span>→</span>
        </button>
        <button className="secondary-button proof-reload" onClick={() => void loadVerifiedProof()} disabled={proofStatus === "loading"}>
          {proofStatus === "loading" ? "Loading cloud proof…" : "Reload verified Gemini proof"}
        </button>
        <p className="runtime-disclosure">
          Fixtures are deterministic and never represented as model output. The verified proof button performs a read-only Firestore mission lookup and never invokes Gemini.
        </p>
        {verifiedProofVisible && (
          <p className="proof-source">
            Verified Cloud Run proof · executable {verifiedProofGitSha.slice(0, 12)} · no new model call
          </p>
        )}
        {health && (
          <dl className="runtime-grid" aria-label="Observed backend configuration">
            <div><dt>runtime</dt><dd>{health.runtime}</dd></div>
            <div><dt>store</dt><dd>{health.store}</dd></div>
            <div><dt>queue</dt><dd>{health.queue}</dd></div>
            <div><dt>gemini</dt><dd>{health.geminiConfigured ? "configured" : "not configured"}</dd></div>
            <div><dt>commit</dt><dd>{health.gitSha.slice(0, 12)}</dd></div>
            <div><dt>proof engine</dt><dd>{mission?.verdict?.engine ?? "loading"}</dd></div>
            <div><dt>LLM calls / run</dt><dd>{health.maxLlmCallsPerMission}</dd></div>
            <div><dt>output cap / call</dt><dd>{health.maxOutputTokensPerCall.toLocaleString()} tok</dd></div>
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
            <p>{proofStatus === "loading" ? "Loading the verified cloud proof…" : "Select a fixture and launch the autonomous review."}</p>
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
              Evidence {mission.verdict.evidence_set_sha256.slice(0, 12)}… · receipt {mission.verdict.receipt_sha256.slice(0, 12)}… · {mission.verdict.engine}
              {mission.next_review_at ? ` · review ${new Date(mission.next_review_at).toLocaleDateString()}` : ""}
            </small>
          </div>
        )}
      </div>
    </section>
  );
}

function FleetControls() {
  return (
    <section className="fleet-controls" id="controls" aria-labelledby="controls-title">
      <p className="eyebrow">Fortified Enterprise Fleet</p>
      <h2 id="controls-title">One catalog gate. Four production boundaries.</h2>
      <div className="control-grid">
        <article><span>01</span><strong>Catalog boundary</strong><p>One bounded AgentCard snapshot is hashed before parallel review; publisher text remains untrusted data.</p></article>
        <article><span>02</span><strong>Async runtime</strong><p>Cloud Run accepts work while Pub/Sub delivers authenticated OIDC jobs and retries failed processing.</p></article>
        <article><span>03</span><strong>Durable lifecycle</strong><p>Firestore persists mission events, linked rechecks, review dates, verdicts, and Git-bound model budgets.</p></article>
        <article><span>04</span><strong>Governance evidence</strong><p>Code-enforced policy, separate evidence and decision hashes, structured logs, and ADK telemetry make every outcome inspectable.</p></article>
      </div>
    </section>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="FourProof Fleet home">
          <span className="brand-mark">4P</span>
          <span>FourProof Fleet</span>
        </a>
        <nav aria-label="Product sections">
          <a href="#mission">Mission control</a>
          <a href="#controls">Fleet controls</a>
          <a href="#architecture">Architecture</a>
        </nav>
        <a className="refresh-button" href="/health" target="_blank" rel="noreferrer">Live health ↗</a>
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
              <a className="primary-button" href="#mission">Inspect the verified proof</a>
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
        <FleetControls />

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
    </div>
  );
}
