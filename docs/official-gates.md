# Official rules evidence and applicant-owned gates

Current official sources: [contest overview](https://allthingsagentichackathon.devpost.com/) and [official rules](https://allthingsagentichackathon.devpost.com/rules). Observed on 2026-08-30. This file records requirements; it does not accept them or certify the applicant.

## Directly observed requirements

- Submission closes August 31, 2026 at 5:00 PM Pacific Time.
- Mainland China is not named in the published residence exclusion list. This is not a complete eligibility determination: age of majority, sanctions/export controls, employment conflicts, employer consent, Internet-access date, and other rule conditions remain applicant-owned checks.
- Every project must genuinely use Gemini 3.5 or newer, at least one listed Google agent framework, and at least one Google Cloud infrastructure service.
- The project must be new during the submission period. Pre-existing code and AI assistance may be used only within the rules and must be disclosed accurately.
- The demonstration video must visibly prove a Google Cloud backend, be no longer than four minutes, be publicly visible on YouTube or Vimeo, and be in English or include English subtitles.
- A hosted project is encouraged. A private repository is allowed only if the required judging accounts receive access.
- The Fortified Enterprise Fleet judging text asks whether the multi-agent complexity is warranted, specialist delegation is real, and the product serves an “unlikely hero” outside standard corporate roles.
- The $150 credit request deadline was August 28, 2026 at noon PT or while supplies lasted. Credits were never guaranteed, so this package assumes no contest credit.

## No-billing alternatives audited

Official Google documentation was rechecked on 2026-08-31 before treating billing as an unavoidable gate:

- [Firebase AI Logic](https://firebase.google.com/docs/ai-logic/get-started?platform=web) can call the Gemini Developer API from a web client on the no-cost Spark plan when protected by production App Check, and [Firestore](https://firebase.google.com/docs/firestore/pricing) has a limited free quota. That path does not run this repository's Python Google ADK backend, durable queue, or fail-closed server policy. Replacing the proven backend with direct client calls would be a different architecture and must not be represented as deployment of FourProof Fleet.
- [Google AI Studio Starter Tier](https://ai.google.dev/gemini-api/docs/aistudio-deploying) can publish up to two eligible full-stack Node.js applications to Cloud Run without a billing account. Google excludes users with an active or prior Google Cloud billing account and some Workspace accounts, and availability is confirmed only in the applicant's AI Studio flow. It is not a drop-in deployment target for this Python ADK container, Firestore transaction store, or Pub/Sub/OIDC queue. No Starter Tier eligibility or publication is claimed.
- [Standard Cloud Run deployment](https://cloud.google.com/run/docs/quickstarts/deploy-container) requires a billing-enabled project. This remains the minimum faithful deployment path for the tested architecture.

The project will not weaken or relabel its architecture merely to obtain a nominal free URL. A different runtime would need its own implementation, tests, architecture, video proof, and truthful framework claims.

## Applicant-owned actions

- Determine personal eligibility and employer-policy compliance.
- Read and accept the binding contest rules and privacy terms.
- Choose the billing-enabled Google Cloud project and state a hard authorization ceiling for the deployment attempt.
- Separately authorize any public Cloud Run access, repository publication or repository sharing, and YouTube/Vimeo publication.
- Verify third-party data, open-source license, reuse, ownership, and AI-assistance disclosures.
- Perform the final Devpost submission and retain its confirmation.

Until each relevant action is explicitly confirmed, its corresponding field in `docs/live-gcp-qa.md` remains `UNVERIFIED`.
