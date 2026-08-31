# Top-five judging scorecard

Source: [official All Things Agentic overview and judging criteria](https://allthingsagentichackathon.devpost.com/). This is a falsifiable internal score, not a placement claim.

| Official criterion | Weight | Current evidence | Current score | Submission gate |
|---|---:|---|---:|---|
| Innovation & Operational Utility | 40 | AI fleet librarian outside the security team; specific enterprise onboarding gate; parallel autonomous evidence collection; code-enforced quarantine; canonical evidence and decision receipts | 35/40 | Keep every claim tied to the submitted demo and public evidence |
| Architectural Discipline & Tech Stack | 30 | Google ADK fan-out/fan-in; immutable evidence snapshot; stable evidence-set hash; run-specific decision receipt; Firestore transaction lease plus Git-bound spend counter; Pub/Sub OIDC; SSRF/prompt-injection boundary; explicit failures; 45 backend tests | 28/30 | Preserve the deployed revision and reproducible proof during judging |
| Demo & Production Readiness | 30 | Responsive UI; architecture PNG/SVG; reproducible setup; public 180.903-second video; verified Cloud Run, Gemini 3.5 Flash, ADK, Firestore, and Pub/Sub execution; submitted Devpost page | 27/30 | Keep the demo, video, repository, and submission publicly reachable |
| **Total** | **100** | **Submission evidence satisfies the core contest proof path** | **90/100** | **Placement remains unverified until official judging results** |

## Evidence that can raise the score

1. `/health` visibly reports `google-cloud-run`, `firestore`, `pubsub`, Gemini configured, model `gemini-3.5-flash`, and ADK 2.8.0.
2. **Live poisoned** uses the deployed JSON URL with no `demo_case`, returns `engine=gemini_adk`, and is forced to quarantine by both model evidence and runtime policy.
3. **Live safe** proves the counterexample: benign content with self-declared identity cannot become production activation.
4. Firestore shows queued → running → completed events, attempt count, lease, evidence hash, and receipt for the same mission id shown in the UI.
5. Firestore shows the atomic live budget document bound to the exact deployed Git SHA, while `/health` proves the per-mission call/output ceilings.
6. A duplicate or forged Pub/Sub request is rejected or idempotently acknowledged without a second execution.
7. `/health` Git SHA, the public repo commit, Cloud Run revision, diagram, submission text, and video all describe the same architecture.

## Current submission evidence

- **Google Cloud:** Cloud Run revision `fourproof-fleet-00014-d5p` serves public commit `6c1c35ce03138fc38b2ceaabb8188f6e31f6b59f` with Firestore and Pub/Sub.
- **Real Gemini/ADK proof:** one non-fixture Gemini 3.5 Flash mission completed through the Google ADK graph and produced a durable quarantine receipt with correlated cloud evidence.
- **Video:** the continuous 180.903-second English demo is public on [YouTube](https://youtu.be/G2iZ4oLoTCE) and visibly demonstrates the Google Cloud backend.
- **Repository:** the clean Fleet source and reproducibility instructions are public in the dedicated [FourProof Fleet repository](https://github.com/tzh476/fourproof-fleet).
- **Devpost:** the project is submitted to the [All Things Agentic Hackathon](https://devpost.com/software/fourproof-fleet).
- **Judging:** shortlist, placement, award, and payment remain unverified until official results.

## Stop conditions

- Do not replace real Cloud proof with screenshots from local fixtures.
- Do not change the linked demo, video, or evidence without revalidating the submission.
- Do not claim top-five placement, winnings, Gemini execution, Google Cloud deployment, or Devpost submission without direct evidence.
