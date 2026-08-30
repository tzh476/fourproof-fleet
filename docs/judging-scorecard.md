# Top-five judging scorecard

Source: [official All Things Agentic overview and judging criteria](https://allthingsagentichackathon.devpost.com/). This is a falsifiable internal score, not a placement claim.

| Official criterion | Weight | Current evidence | Current score | Submission gate |
|---|---:|---|---:|---|
| Innovation & Operational Utility | 40 | Unlikely hero is an AI fleet librarian outside the security team; specific enterprise onboarding gate; real catalog context; parallel autonomous evidence collection; code-enforced quarantine; canonical receipt | 33/40 | Show two non-fixture Gemini missions and a linked re-review across durable state |
| Architectural Discipline & Tech Stack | 30 | Google ADK fan-out/fan-in; one immutable evidence snapshot; stable evidence-set hash; run-specific decision receipt; Firestore transaction lease plus Git-bound spend counter; 8-call/2,048-output-token ceilings; Pub/Sub OIDC; SSRF/prompt-injection boundary; explicit failures; 42 backend tests | 27/30 | Prove the same graph, store, queue, lease, budget, and failure behavior on Google Cloud |
| Demo & Production Readiness | 30 | Polished responsive UI; architecture SVG/PNG; reproducible setup; 3:35 script; deterministic local proof | 13/30 | Record a continuous real Cloud Run/Vertex AI/Firestore/Pub/Sub demo and publish it |
| **Total** | **100** | **Strong local candidate; cloud proof is the critical path** | **73/100** | **Do not submit below 88/100** |

## Evidence that can raise the score

1. `/health` visibly reports `google-cloud-run`, `firestore`, `pubsub`, Gemini configured, model `gemini-3.5-flash`, and ADK 2.8.0.
2. **Live poisoned** uses the deployed JSON URL with no `demo_case`, returns `engine=gemini_adk`, and is forced to quarantine by both model evidence and runtime policy.
3. **Live safe** proves the counterexample: benign content with self-declared identity cannot become production activation.
4. Firestore shows queued → running → completed events, attempt count, lease, evidence hash, and receipt for the same mission id shown in the UI.
5. Firestore shows the atomic live budget document bound to the exact deployed Git SHA, while `/health` proves the per-mission call/output ceilings.
6. A duplicate or forged Pub/Sub request is rejected or idempotently acknowledged without a second execution.
7. `/health` Git SHA, the public repo commit, Cloud Run revision, diagram, submission text, and video all describe the same architecture.

## Top-five blockers, in order

- **GCP authority/cost:** the currently selected project exists but has billing disabled and the required APIs disabled. The applicant must choose or create a billing-enabled project and explicitly authorize resource creation.
- **No contest credits assumed:** the official $150 credit request deadline was August 28 at noon PT and credits were never guaranteed; deployment requires a separately approved self-funded ceiling.
- **Real Gemini proof:** no API key or Vertex AI execution has been observed; deterministic fixtures do not count.
- **Video:** no continuous public video exists. The final English or English-subtitled take must be no longer than four minutes, visibly prove the Google Cloud backend, and be publicly visible on YouTube or Vimeo.
- **Repository publication:** the clean Fleet commit must be published to its own repository, not pushed to the inherited FourProof BNB repository.
- **Devpost:** joining, eligibility/rules/privacy declarations, any media publication, and final submit remain applicant-owned actions.

## Stop conditions

- Do not replace real Cloud proof with screenshots from local fixtures.
- Do not spend time on optional social/blog bonuses before the 88/100 core gate is met.
- Do not claim top-five placement, winnings, Gemini execution, Google Cloud deployment, or Devpost submission without direct evidence.
