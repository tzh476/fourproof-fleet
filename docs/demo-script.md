# FourProof Fleet demo script (target: 3:35)

The final recording must use the real Cloud Run deployment and a real `gemini_adk` mission. Replace bracketed fields only after observing them.

## 0:00-0:25 — Problem

“Enterprise teams are about to hire thousands of third-party agents. Their AgentCards make discovery easy, but the cards are publisher-controlled input. One poisoned card can ask a reviewer to ignore policy, leak credentials, or call a private endpoint. FourProof Fleet puts a zero-trust review gate between discovery and enterprise tools.”

Show the hero and the three policy outcomes.

## 0:25-0:55 — Architecture

“An operator submits one AgentCard. Cloud Run accepts the mission, Firestore stores its durable state, and Pub/Sub triggers an authenticated worker. A Google ADK workflow fans out to Registry Scout, Identity Verifier, and Tool Guard. Gemini 3.5 Flash produces typed reports, then Policy Judge fans them back in. The result is sealed to a canonical SHA-256 receipt.”

Show `docs/architecture.svg`, then `/healthz` with `[MODEL]`, `google-adk`, `firestore`, `pubsub`, and `cloud_run` visible.

## 0:55-2:05 — Poisoned mission

“This is a real external AgentCard, not the deterministic fixture. It contains an instruction override, a secret-exfiltration request, tool coercion, role impersonation, and a loopback endpoint.”

Select **Live poisoned**. It submits `[CLOUD_RUN_URL]/agentcards/poisoned.json` without a `demo_case`; keep the timeline visible.

“The specialists execute independently. Registry Scout hashes the exact inspected bytes. Identity Verifier refuses to turn a publisher claim into verified identity. Tool Guard blocks the endpoint before connection. Policy Judge returns quarantine, with evidence from every specialist. The UI shows `engine=gemini_adk`, model `gemini-3.5-flash`, and receipt `[RECEIPT_PREFIX]`.”

Open the Firestore document for the same mission id and briefly show the terminal event.

## 2:05-2:40 — Safe counterexample

“Now a benign card. Absence of an obvious attack is not enough for production access. Missing independent identity evidence keeps the outcome at human review or isolated sandbox. FourProof never translates a clean-looking card into unrestricted activation.”

Select **Live safe**. It submits `[CLOUD_RUN_URL]/agentcards/safe.json` without a `demo_case`; show the bounded decision and its reasons.

## 2:40-3:15 — Cloud and recovery proof

“The worker is decoupled through Pub/Sub with Google OIDC audience and service-account verification. Firestore keeps the event stream across Cloud Run instances. Duplicate terminal deliveries are idempotent, failures are explicit, and scale-to-zero plus a bounded maximum controls cost.”

Show the Cloud Run revision, Pub/Sub authenticated push configuration, and Firestore mission sequence. Do not expose account, token, project-secret, or billing details.

Trigger one linked recheck for the safe mission and show `previous_mission_id`, `next_review_at`, and the unchanged receipt when the underlying evidence bytes are unchanged.

## 3:15-3:35 — Close

“Agent discovery answers ‘what can I hire?’ FourProof Fleet answers ‘what evidence is safe enough to test?’ It turns untrusted agent metadata into a reproducible, fail-closed onboarding decision—before any agent sees enterprise secrets or tools.”

End on the verdict and full receipt.
