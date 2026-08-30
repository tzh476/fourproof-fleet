# Threat model

## Protected assets

- operator and service credentials;
- private network endpoints;
- production tool access;
- mission integrity and verdict provenance;
- identity claims and evidence receipts.

## Adversarial cases

| Attack | Control | Verification |
|---|---|---|
| AgentCard says to ignore prior instructions | Content is treated as quoted data; explicit override patterns are surfaced | `test_poisoned_card_triggers_all_four_signals` |
| AgentCard requests secrets or shell execution | No secret/tool capability is exposed; exfiltration and coercion patterns quarantine | agent and API poisoned-fixture tests |
| Target points to localhost, metadata, or a private address | Scheme, credentials, hostname, IP class, and DNS results are checked before fetch | URL safety unit tests |
| Public URL redirects into a private network | Redirects are disabled | live fetch implementation and safety tests |
| Oversized or non-JSON response | Response is capped at 256 KB and parsed as JSON | bounded fetch path |
| Publisher claims a verified owner | Declared identity remains `declared` or `missing`; it is not promoted to verified | safe-fixture counterexample test |
| Forged Pub/Sub request | Google OIDC token, issuer, audience, and exact service-account email are verified | internal push API tests |
| Pub/Sub redelivers a completed mission | Terminal missions return success without re-execution | terminal idempotency API test |
| Gemini returns malformed output | Pydantic schemas reject it and the mission fails closed | typed ADK outputs plus failure handling |
| Public demo is abused to scan arbitrary hosts or spend model budget | Exact live-target hostname allowlist; transactional per-Git mission ceiling; eight-call and 2,048-output-token per-call ceilings; one Cloud Run instance | API, ADK graph, store concurrency, live-proof, and deployment guard tests |

## Residual risks

- DNS rebinding between resolution and connection is reduced but not eliminated by the application-level check; an egress proxy with destination enforcement is the stronger production control.
- The injection detector is deliberately explainable and incomplete. Novel semantic attacks still require Gemini judgment and human review.
- Registry and owner fields are discovery claims. Direct chain or issuer verification is not yet implemented.
- Firestore updates are read/replace operations rather than transactional event appends; concurrent workers are contained by terminal-state checks but a lease/transaction is needed for stronger exactly-once behavior.
- `allow_sandbox` is not proof that an agent is safe. It means only that the observed evidence permits isolated testing under separate runtime controls.
- The Firestore mission ceiling is global for one deployed Git SHA, but it does not cap Cloud Run traffic, storage retention, build retries, logging, egress, or a later revision. Public hosting therefore still needs a separately authorized window, monitoring, and cleanup.
- The included deployment grants project-level service-account roles for a rapid hackathon deployment. A production rollout should isolate projects and narrow IAM permissions further.
