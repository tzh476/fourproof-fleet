# Continuous four-minute recording runbook

This runbook records how the final continuous demo was produced after `scripts/live_proof.py` passed against the final Cloud Run revision. The resulting 180.903-second English video is public at `https://youtu.be/G2iZ4oLoTCE` and is linked from the submitted Devpost entry. The official limit is four minutes.

## Before pressing record

- Use the exact Git SHA, Cloud Run URL, and remaining live-mission budget recorded by the proof script.
- Open only these prepared tabs: product UI, `/health`, architecture PNG, Cloud Run revision, Firestore mission document, Pub/Sub subscription.
- Collapse account menus and hide project/account identifiers that are not necessary evidence.
- Close terminals or browser tabs containing tokens, billing details, email, cookies, environment variables, or unrelated work.
- Set browser zoom so the `.run.app` hostname, verdict, evidence-set hash, receipt, and mission id remain legible.
- Rehearse once without recording. Do not use fixture buttons in the final recording.

## One continuous take

| Time | Screen | Non-negotiable evidence |
|---|---|---|
| 0:00–0:25 | Hero | Specific enterprise AgentCard onboarding problem and three bounded outcomes |
| 0:25–0:55 | Architecture → `/health` | Cloud Run, Firestore, Pub/Sub, Gemini 3.5 Flash, Google ADK 2.8.0, allowlist, final Git SHA, 8-call/2,048-token ceilings |
| 0:55–2:05 | Live poisoned | `.run.app/agentcards/poisoned.json`, no `demo_case`, `engine=gemini_adk`, blocked guard, quarantine, evidence-set hash, receipt |
| 2:05–2:40 | Live safe | Benign card remains human review or isolated sandbox; never production activation |
| 2:40–3:15 | Firestore → Pub/Sub → logs | Same mission id, durable terminal document and Git-bound budget, authenticated OIDC audience, correlated structured log |
| 3:15–3:35 | Linked recheck → close | Previous mission id, next review date, stable evidence-set hash; explicitly allow a run-specific receipt to differ |

## Truth checks before upload

- The take is continuous and approximately four minutes.
- The exported video is no longer than four minutes and is ready for a publicly visible YouTube or Vimeo upload.
- The spoken presentation is English, or accurate English subtitles are present.
- Every cloud claim visible in the take exists in `docs/live-gcp-proof.json` or a captured console panel.
- Deterministic local fixtures are not shown as Gemini execution.
- The spoken model, framework, Git SHA, service revision, mission id, action, evidence hash, and receipt match the screen.
- No claim says that identical evidence guarantees identical model prose or identical run-specific receipts.
- No account identity, secret, credential, billing detail, or private repository URL is visible.
- The applicant reviews the final media file before authorizing publication.
