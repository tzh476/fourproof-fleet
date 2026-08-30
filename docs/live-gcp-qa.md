# Live Google Cloud QA record

Evidence was observed directly on 2026-08-31 (Asia/Shanghai). Fields that were
not exercised remain `UNVERIFIED`; expected behavior is not copied into the
evidence column.

| Check | Result | Evidence |
|---|---|---|
| Final Git commit | VERIFIED | `6c1c35ce03138fc38b2ceaabb8188f6e31f6b59f`, public `main` |
| `/health` Git SHA match | VERIFIED | health response and Cloud Run environment matched `6c1c35c…` |
| Cloud Run URL | VERIFIED | `https://fourproof-fleet-7bow5ev35a-uc.a.run.app` |
| Cloud Run revision | VERIFIED | `fourproof-fleet-00014-d5p`, 100% latest traffic |
| `/health` runtime | VERIFIED | `google-cloud-run` |
| `/health` store | VERIFIED | `firestore` |
| `/health` queue | VERIFIED | `pubsub` |
| `/health` model/framework | VERIFIED | `gemini-3.5-flash`, Google ADK `2.8.0` |
| `/health` live mission/call/output limits | VERIFIED | 8 missions, 8 calls per mission, 2,048 output tokens per call |
| Real poisoned mission id | VERIFIED | `aa919f3ac5eb4cf68c0aed1b51d721f8` |
| Real poisoned engine/verdict | VERIFIED | `gemini_adk`, `quarantine`, terminal `completed` |
| Real poisoned receipt | VERIFIED | `e3b50bcb3d5b23e4a54733e56820abbf11ec7449c20080429ab11cb260f9708a` |
| Real poisoned evidence-set hash | VERIFIED | `39d8f18220d209f88812a08905877c80e41a1c50b8d362b51e2bde64623b5f7c` |
| Mission event stages | VERIFIED | intake, runtime, scout, identity, guard, judge, receipt |
| Safe counterexample mission id/verdict | UNVERIFIED | no safe live mission was required or represented in the final proof |
| Firestore mission persistence | VERIFIED | proof reader observed the terminal mission document after a new Cloud Run instance start |
| Firestore Git-bound live budget used/limit | VERIFIED | `1 / 8`, previously `0 / 8` for the final Git SHA |
| Pub/Sub authenticated delivery | VERIFIED | mission completed through the configured OIDC push subscription |
| Forged push rejection | UNVERIFIED | covered by local tests; not repeated as a live cloud mutation |
| Cloud Logging mission correlation | VERIFIED | six entries observed for the exact mission id |
| Automated sanitized live-proof JSON | VERIFIED | [`live-gcp-proof.json`](live-gcp-proof.json) |
| Billing/project usage after proof vs applicant ceiling | UNVERIFIED | no provider-enforced USD hard cap is claimed |
| Local final video duration ≤4:00 | VERIFIED | 180.902667 seconds, 1920×1080 H.264/AAC, full decode passed |
| Public YouTube/Vimeo URL | UNVERIFIED | publication remains applicant-owned |
| Devpost receipt | UNVERIFIED | project creation remains CAPTCHA-gated; no submission claimed |
