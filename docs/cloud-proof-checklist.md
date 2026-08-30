# Google Cloud proof checklist

Do not claim Google Cloud execution until every applicable item has direct evidence.

## Before deployment

- [ ] The applicant selected and authenticated the intended `gcloud` account.
- [ ] The applicant confirmed the project, billing status, contest eligibility, and resource cost.
- [ ] No contest credits are assumed; the applicant supplied a self-funded hard authorization ceiling.
- [ ] Public Cloud Run access has a separate applicant authorization; otherwise the deployment remains private.
- [ ] `FOURPROOF_PROJECT_ID`, region, service name, and runtime service account were reviewed.
- [ ] No key, ADC file, cookie, or token is in Git history.

## Runtime proof

- [ ] Cloud Run revision is built from the final Git commit.
- [ ] `/health` `gitSha` exactly matches the public repository's final commit.
- [ ] `/health` reports `runtime=google-cloud-run`, `store=firestore`, `queue=pubsub`, `geminiConfigured=true`.
- [ ] The model shown by `/health` is exactly `gemini-3.5-flash` and the framework is Google ADK.
- [ ] `/health` reports the applicant-approved total live-mission limit, exactly 8 LLM calls per mission, and 2,048 output tokens per call.
- [ ] A non-fixture mission finishes with `engine=gemini_adk`; deterministic output does not count.
- [ ] Firestore contains the queued, running, and terminal events for the demonstrated mission.
- [ ] Firestore contains `_live_budget_<git-sha>` with the exact Git SHA, configured limit, observed use, and at least one remaining mission for judging.
- [ ] Pub/Sub delivery uses authenticated OIDC and the configured audience/service-account binding.
- [ ] The completed mission survives a new Cloud Run instance or restart.
- [ ] Cloud Logging shows the same mission id without exposed input secrets.
- [ ] `scripts/live_proof.py` exits successfully and its sanitized JSON is reviewed against the console before publication.

## Counterexamples

- [ ] A poisoned AgentCard is quarantined and lists each blocking reason.
- [ ] A benign but unverified AgentCard cannot receive production activation; it ends in human review or an isolated sandbox.
- [ ] A private-network URL is rejected before any outbound request.
- [ ] A forged internal push request receives 401/403.

## Cost and operations

- [ ] Cloud Run min instances is zero and max instances is bounded.
- [ ] `docs/cost-boundary.md` was reviewed against current official prices; the approved proof ceiling is at least USD 5 and is not represented as an automatic provider hard stop.
- [ ] Firestore and Pub/Sub usage are inspected after the demo.
- [ ] A budget alert or explicit cleanup plan exists.
- [ ] Temporary resources are removed after judging if they are no longer required.

## Submission capture

- [ ] The public demo URL and public repository URL are final.
- [ ] The English or English-subtitled video is no longer than four minutes and is publicly visible on YouTube or Vimeo.
- [ ] The video shows the real Cloud Run hostname, `/health`, one real Gemini mission, Firestore events, and the sealed receipt in one continuous narrative.
- [ ] The video distinguishes the stable evidence-set hash from the run-specific decision receipt.
- [ ] The architecture image is uploaded and legible.
- [ ] All reuse, AI-assistance, eligibility, privacy, and rules declarations were reviewed and accepted by the applicant personally.
- [ ] Final Devpost submit is performed by the applicant and the confirmation receipt is saved.

Record verified values in `docs/live-gcp-qa.md`; do not pre-fill unobserved values.
