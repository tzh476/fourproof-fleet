# Devpost submission copy

This is the evidence-backed working copy for the submitted [FourProof Fleet Devpost entry](https://devpost.com/software/fourproof-fleet). The public project page and authenticated manage page were verified after submission on 2026-08-31.

## Project name

FourProof Fleet

## Tagline

Hire the agent. Not the risk.

## Category

Fortified Enterprise Fleet

## One-line pitch

FourProof Fleet is a Google ADK and Gemini 3.5 zero-trust gate that reviews third-party AgentCards in parallel, quarantines unsafe agents, and seals exact evidence plus every decision into separate tamper-evident hashes.

## Inspiration

Agent registries are becoming app stores for autonomous software. They make agents discoverable, but discovery metadata is still supplied by the publisher. Our unlikely hero is the AI fleet librarian: an operations coordinator asked to catalog autonomous software without having to become a security engineer. FourProof Fleet gives that person a boundary between “this agent exists” and “this agent may touch our tools, data, or credentials,” turning onboarding into an evidence-producing workflow instead of a trust-by-description decision.

## What it does

An operator submits an AgentCard URL. Three independent specialists run in parallel:

- Registry Scout performs a bounded fetch, records provenance, and hashes the exact inspected evidence.
- Identity Verifier separates declared owner and registry fields from independently verified facts.
- Tool Guard detects prompt injection, secret exfiltration, tool coercion, role impersonation, credential-bearing URLs, and private-network targets.

A Policy Judge combines the typed reports and returns only one of three bounded outcomes: isolated sandbox, human review, or quarantine. A receipt sealer produces a stable evidence-set hash plus a run-specific SHA-256 decision receipt. The UI exposes the full mission timeline, engine, model, reasons, both hashes, and next lifecycle review date. A linked recheck preserves the previous mission id, allowing an enterprise to compare exact evidence across long-running review cycles without pretending Gemini wording is deterministic.

## How we built it

The backend is FastAPI on Cloud Run. Mission state and event history live in Firestore. Pub/Sub decouples intake from execution and authenticates push deliveries with Google OIDC. Google ADK 2.8 defines a fan-out/fan-in `Workflow`: Registry Scout, Identity Verifier, and Tool Guard run concurrently, then Policy Judge runs after all three complete. Gemini 3.5 Flash (`gemini-3.5-flash`) powers typed specialist reports and the policy decision. ADK's OpenTelemetry instrumentation and secret-free structured Cloud Logging events share the mission id for end-to-end correlation.

The security boundary validates URL schemes and credentials, resolves DNS, rejects private and reserved destinations, disables redirects, caps responses at 256 KB, and never sends target content a secret or production tool. Model outputs are validated with Pydantic. Real Gemini missions are transactionally capped per deployed Git SHA, each mission allows at most eight model calls, and each call allows at most 2,048 output tokens. Uncaught errors become explicit failed missions rather than activation decisions.

## Challenges we ran into

The hardest design problem was preventing the reviewer from becoming the attack surface. A naive “send this URL to an LLM” implementation risks SSRF, prompt injection, and false identity claims. We therefore separated bounded evidence collection from model judgment, removed redirects and credentials, used typed outputs, and treated all card text as quoted evidence. Another challenge was making retries auditable: queue redelivery, durable state, terminal idempotency, and failure events had to agree. Live Gemini runs exposed real schema variation—one verdict returned a scalar where a list was expected—so we added bounded normalization for known scalar fields while continuing to reject unknown evidence identifiers. The final non-fixture mission completed without weakening the fail-closed boundary.

## Accomplishments that we are proud of

- A real Google ADK graph with three concurrent specialists and one fan-in judge.
- Explainable fail-closed outcomes instead of a generic safety score.
- Stable exact-evidence hashing plus run-specific decision receipts.
- An authenticated Pub/Sub/Cloud Run boundary with durable Firestore events.
- Explicit runtime disclosure: deterministic fixtures cannot masquerade as Gemini or Google Cloud execution.
- A durable, Git-bound live mission budget plus per-run model-call and output-token ceilings.
- Adversarial tests for prompt injection, SSRF, forged queue delivery, duplicate execution, and benign-but-unverified agents.
- A completed non-fixture Gemini 3.5 Flash mission on the exact public Git SHA, with a quarantine verdict, all seven expected stages, durable Firestore state, Pub/Sub delivery, six correlated Cloud Logging entries, and separate evidence/decision hashes.

## What we learned

Agent identity, capability, and safety are different claims. Registry presence proves discovery, not ownership or safe behavior. Parallel reviewers improve coverage only if their evidence remains independent and a final policy remains bounded. We also learned that provenance is a product feature: showing the engine, model, state transitions, and receipt makes a verdict inspectable rather than magical.

## What's next

- lease heartbeats and transactional event appends for stronger crash recovery;
- controlled egress through a destination-enforcing proxy;
- signed policy bundles and organization-specific approval thresholds;
- continuous re-review when an AgentCard, endpoint, or on-chain identity changes.

## Built with

Gemini 3.5 Flash, Google Agent Development Kit, Cloud Run, Firestore, Pub/Sub, Cloud Logging, Vertex AI, FastAPI, Pydantic, React, TypeScript, and Vite.

## Links

- Demo: `https://fourproof-fleet-7bow5ev35a-uc.a.run.app`
- Repository: `https://github.com/tzh476/fourproof-fleet`
- Video: `https://youtu.be/G2iZ4oLoTCE`
- Architecture: `https://github.com/tzh476/fourproof-fleet/blob/main/docs/architecture.svg`

## Reproducibility

Run `npm run check` for frontend tests, backend/security tests, TypeScript checking, and a production build. Local deterministic fixtures are clearly labeled and require no credentials. The final video is bound to public commit `6c1c35ce03138fc38b2ceaabb8188f6e31f6b59f` and shows the sanitized state of a separate real Gemini/ADK mission with `engine=gemini_adk`; `docs/live-gcp-proof.json` records the exact observed cloud evidence without credentials or billing identifiers.

## Contest-period disclosure

FourProof Fleet was created specifically for the All Things Agentic Hackathon during the contest submission period. Its Google ADK workflow, Gemini agent graph, mission API, safety boundary, Firestore/Pub/Sub execution, evidence receipts, deployment materials, and enterprise onboarding flow were built for this entry.

## Submission evidence

- Devpost: `https://devpost.com/software/fourproof-fleet` — submitted to the All Things Agentic Hackathon.
- Public demo: `https://fourproof-fleet-7bow5ev35a-uc.a.run.app` — Cloud Run health and UI verified.
- Public repository: `https://github.com/tzh476/fourproof-fleet` — reproducibility instructions, architecture, tests, and sanitized cloud proof.
- Public video: `https://youtu.be/G2iZ4oLoTCE` — 180.903-second English demo with visible Google Cloud backend proof.
