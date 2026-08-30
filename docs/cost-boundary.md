# Google Cloud cost boundary and action gates

This is a conservative pre-deployment model, not a bill, credit claim, or automatic Google Cloud spending cap. It uses public list prices observed on 2026-08-30 and assumes `us-central1`, request-based Cloud Run, one source build, at most eight real Gemini missions, and prompt sizes within the application's bounded evidence design. The applicant must inspect the selected billing account's existing usage and approve the project plus USD ceiling at action time.

## Code-enforced workload bounds

- `FOURPROOF_MAX_LIVE_MISSIONS` must be exactly 8. Firestore reserves each real Gemini mission atomically in `_live_budget_<git-sha>`; deterministic fixtures do not consume it.
- Google ADK `RunConfig` allows at most eight model calls in one mission. The SDK default of 500 is not used.
- Every specialist and judge call has `max_output_tokens=2048`.
- AgentCard fetches are no larger than 256 KB, redirects are disabled, and only a bounded 8,000-character serialized excerpt can enter the Scout tool result.
- Cloud Run uses request-based billing, zero minimum instances, one maximum instance, 1 vCPU, 1 GiB RAM, and a 300-second request timeout.

## Conservative eight-mission proof envelope

Google lists standard global Gemini 3.5 Flash at USD 1.50 per million input tokens and USD 9.00 per million text output/reasoning tokens. The local code does not pretend to know live token counts before the first authorized run, so this estimate deliberately allocates 20,000 input tokens to every possible model call and the full 2,048 output-token limit:

```text
model calls       = 8 missions × 8 calls = 64 calls
input estimate    = 64 × 20,000 / 1,000,000 × $1.50 = $1.920000
output maximum    = 64 × 2,048  / 1,000,000 × $9.00 = $1.179648
Gemini subtotal   = $3.099648
```

This is an estimate, not a strict input-token cap. The call count and output tokens are code-enforced; actual input billing must be read from the live Vertex AI usage evidence.

For infrastructure, the deliberately pessimistic proof estimate assumes every mission occupies the full 300-second Cloud Run timeout, a 30-minute `e2-standard-2` source build, one 1 GiB artifact retained for a month, and no remaining free-tier allowance:

| Component | Pessimistic proof calculation | Estimated USD |
|---|---:|---:|
| Cloud Run CPU + RAM | `2,400 s × ($0.000024 + $0.0000025)` | 0.0636 |
| Cloud Run requests | 10,000 requests × $0.40 / 1M | 0.0040 |
| Cloud Build | 30 min × $0.006 | 0.1800 |
| Artifact Registry | 0.5 GiB-month above the 0.5 GiB free tier | about 0.0500 |
| Firestore + Pub/Sub | proof-scale reads/writes/messages | under 0.0010 |
| **Modeled total including Gemini** | | **about 3.40** |

The same official pages report monthly/daily free allowances that should cover this infrastructure workload when unused: Cloud Run includes 180,000 request-based vCPU-seconds, 360,000 GiB-seconds, and 2 million requests; Cloud Build includes 2,500 build minutes per billing account; Artifact Registry includes 0.5 GiB-month; Firestore includes 50,000 reads and 20,000 writes per day; Pub/Sub includes 10 GiB throughput per month. Free quotas are shared and cannot be assumed available.

Official sources:

- [Gemini on Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Cloud Build pricing](https://cloud.google.com/build/pricing)
- [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing)
- [Firestore pricing](https://cloud.google.com/firestore/pricing)
- [Pub/Sub pricing](https://cloud.google.com/pubsub/pricing)
- [Cloud Billing budget behavior](https://cloud.google.com/billing/docs/how-to/budgets)

## Authorization recommendation

For one private deployment, automated three-mission proof, recording rehearsal, and no more than eight live missions total, the prepared script requires an applicant-approved ceiling of at least **USD 5**. This gives roughly USD 1.60 headroom above the conservative proof estimate. It does not authorize spending by itself; the separate exact acknowledgement is still required immediately before deployment.

Do not confuse that USD 5 authorization with a provider-enforced hard stop. Google states that alerts-only budgets do not automatically cap usage or spending, and billing data can lag. The app's Firestore/model ceilings bound the main Gemini driver, but they do not bound public HTTP traffic, build retries, logging, egress, storage retention, a redeploy with a new Git SHA, or unrelated usage in the same billing account.

## Public-hosting gate

The USD 5 model covers the controlled deployment/proof workload only. A publicly invokable Cloud Run service has unbounded incoming traffic even with one maximum instance. At list price and with no free allowance, one continuously active 1 vCPU / 1 GiB instance is roughly:

```text
($0.000024 + $0.0000025) × 86,400 seconds ≈ $2.29 per day
```

Therefore public `allUsers` access requires a second action-time authorization and an explicit exposure/cleanup decision. The deployment remains private unless `FOURPROOF_PUBLIC_DEMO_ACK` is separately set. Do not claim a hard public-hosting cap that Google Cloud and this application cannot guarantee.

## Required action sequence

1. Applicant provides the exact billing-enabled project id, confirms `us-central1` or another priced region, and states a self-funded USD ceiling of at least 5.
2. Applicant reviews this model and separately authorizes the billable deployment acknowledgement. Only then may the deployment script enable APIs, create IAM/resources, and deploy privately.
3. Applicant separately authorizes live Gemini proof. The proof script consumes three of the revision's mission budget and captures the exact budget counter.
4. Applicant separately authorizes public Cloud Run access for recording/judging and chooses when public access/resources will be removed.
5. After proof/recording, inspect billing and Vertex usage. If the observed trajectory conflicts with the approved ceiling, remove public access and stop; do not start more missions or redeploy.
