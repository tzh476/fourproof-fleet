# Devpost submission draft

This is working copy, not a submitted entry. The applicant must verify every declaration and perform the final submission personally.

## Project name

FourProof Fleet

## Tagline

Hire the agent. Not the risk.

## Category

Fortified Enterprise Fleet

## One-line pitch

FourProof Fleet is a Google ADK and Gemini 3.5 zero-trust gate that reviews third-party AgentCards in parallel, quarantines unsafe agents, and seals every decision to a reproducible evidence receipt.

## Inspiration

Agent registries are becoming app stores for autonomous software. They make agents discoverable, but discovery metadata is still supplied by the publisher. Enterprises need a boundary between “this agent exists” and “this agent may touch our tools, data, or credentials.” FourProof Fleet turns onboarding into an evidence-producing workflow instead of a trust-by-description decision.

## What it does

An operator submits an AgentCard URL. Three independent specialists run in parallel:

- Registry Scout performs a bounded fetch, records provenance, and hashes the exact inspected evidence.
- Identity Verifier separates declared owner and registry fields from independently verified facts.
- Tool Guard detects prompt injection, secret exfiltration, tool coercion, role impersonation, credential-bearing URLs, and private-network targets.

A Policy Judge combines the typed reports and returns only one of three bounded outcomes: isolated sandbox, human review, or quarantine. A receipt sealer canonicalizes the evidence and produces a SHA-256 decision receipt. The UI exposes the full mission timeline, engine, model, reasons, receipt, and next lifecycle review date. A linked recheck preserves the previous mission id, allowing an enterprise to compare evidence across long-running review cycles.

## How we built it

The backend is FastAPI on Cloud Run. Mission state and event history live in Firestore. Pub/Sub decouples intake from execution and authenticates push deliveries with Google OIDC. Google ADK 2.8 defines a fan-out/fan-in `Workflow`: Registry Scout, Identity Verifier, and Tool Guard run concurrently, then Policy Judge runs after all three complete. Gemini 3.5 Flash (`gemini-3.5-flash`) powers typed specialist reports and the policy decision. ADK's OpenTelemetry instrumentation and secret-free structured Cloud Logging events share the mission id for end-to-end correlation.

The security boundary validates URL schemes and credentials, resolves DNS, rejects private and reserved destinations, disables redirects, caps responses at 256 KB, and never sends target content a secret or production tool. Model outputs are validated with Pydantic. Uncaught errors become explicit failed missions rather than activation decisions.

The React/Vite frontend also includes read-only BSC ERC-8004 identity discovery across four categories. The live registry is context; its metadata is never treated as proof of enterprise safety.

## Challenges we ran into

The hardest design problem was preventing the reviewer from becoming the attack surface. A naive “send this URL to an LLM” implementation risks SSRF, prompt injection, and false identity claims. We therefore separated bounded evidence collection from model judgment, removed redirects and credentials, used typed outputs, and treated all card text as quoted evidence. Another challenge was making retries auditable: queue redelivery, durable state, terminal idempotency, and failure events had to agree.

## Accomplishments that we are proud of

- A real Google ADK graph with three concurrent specialists and one fan-in judge.
- Explainable fail-closed outcomes instead of a generic safety score.
- Exact evidence and decision hashing for reproducible receipts.
- An authenticated Pub/Sub/Cloud Run boundary with durable Firestore events.
- Explicit runtime disclosure: deterministic fixtures cannot masquerade as Gemini or Google Cloud execution.
- Adversarial tests for prompt injection, SSRF, forged queue delivery, duplicate execution, and benign-but-unverified agents.

## What we learned

Agent identity, capability, and safety are different claims. Registry presence proves discovery, not ownership or safe behavior. Parallel reviewers improve coverage only if their evidence remains independent and a final policy remains bounded. We also learned that provenance is a product feature: showing the engine, model, state transitions, and receipt makes a verdict inspectable rather than magical.

## What's next

- direct ERC-8004 owner and registration-event verification;
- lease heartbeats and transactional event appends for stronger crash recovery;
- controlled egress through a destination-enforcing proxy;
- signed policy bundles and organization-specific approval thresholds;
- continuous re-review when an AgentCard, endpoint, or on-chain identity changes.

## Built with

Gemini 3.5 Flash, Google Agent Development Kit, Cloud Run, Firestore, Pub/Sub, Cloud Logging, Vertex AI, FastAPI, Pydantic, React, TypeScript, Vite, viem, BSC ERC-8004.

## Links (replace after live verification)

- Demo: `[TBD_CLOUD_RUN_URL]`
- Repository: `[TBD_PUBLIC_REPOSITORY_URL]`
- Video: `[TBD_PUBLIC_VIDEO_URL]`
- Architecture: `docs/architecture.svg`

## Reproducibility

Run `npm run check` for frontend tests, backend/security tests, TypeScript checking, and a production build. Local deterministic fixtures are clearly labeled and require no credentials. The submitted video must show a separate real Gemini/ADK mission with `engine=gemini_adk` and live Google Cloud state.

## Contest-period and reused-work disclosure

FourProof Fleet was created during the contest period. It adapts the UI, BSC discovery proxy, registry ranking, and read-only evidence concepts from FourProof BNB, first created on 2026-08-29, also within the contest period. The Google ADK workflow, Gemini graph, mission API, safety boundary, Firestore/Pub/Sub execution, evidence receipt, deployment materials, and enterprise onboarding flow are new for FourProof Fleet. Codex was used as a coding assistant.

## Applicant-owned final checks

- Confirm the project and reused-work disclosure satisfy the official rules.
- Confirm every team member, eligibility, privacy, IP, and AI-assistance statement.
- Accept any rules, terms, or declarations personally.
- Verify the public demo, repository, video, architecture, and all written claims.
- Perform the final Devpost submission and preserve the receipt.
