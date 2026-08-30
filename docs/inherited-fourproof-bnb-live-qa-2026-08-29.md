# Inherited FourProof BNB live QA — 2026-08-29

> Historical evidence for the reused BSC discovery UI only. It is not FourProof Fleet Gemini, ADK, or Google Cloud proof.

This report records observed behavior, not an endorsement of any indexed agent.

## Marketplace smoke check

- The local app loaded live BSC data for all four required categories.
- Two refreshes produced 15 and then 14 ranked category entries as the live search results changed. Entries can repeat across categories, so these are not unique-agent counts.
- Direct `ownerOf` and `tokenURI` reads for ERC-8004 token `269223` succeeded against the canonical BSC registry. The indexed owner matched at observed block `118769100`.
- At this stage no wallet connection, transaction, funded ERC-8183 job, or contest submission was performed.

## Discovery versus execution counterexamples

### ERC-8004 token 269223

- 8004scan reported the A2A AgentCard as healthy, while domain verification failed with HTTP 404.
- The live AgentCard declared its actual service URL as `http://127.0.0.1:9101/`.
- Conclusion: the discovery document was publicly readable, but its execution target was not publicly usable.

### ERC-8004 token 303779

- 8004scan reported a healthy AgentCard but skipped domain verification because it used a third-party hosting domain.
- The AgentCard declared a public A2A target and negotiation skills.
- One bounded, non-financial JSON-RPC `message/send` smoke request asked for a hypothetical read-only grid plan. The endpoint returned HTTP 500 with `INTERNAL_ERROR` and the message `The seller request failed.`
- No wallet data, personal data, funds, trade instruction, or onchain action was included. The failed response gave no evidence that external state was created, and the request was not retried.

## Product correction

The original MVP treated a healthy discovery document plus a published wallet as operational evidence. That was too optimistic. The implementation now:

1. labels scanner health as AgentCard/service-metadata health;
2. requires verified discovery-domain ownership;
3. requires a separately resolved execution target and a successful bounded public-call check;
4. requires a fresh direct BSC owner proof before local activation-plan generation; and
5. keeps every currently unvalidated live candidate below the operational tier.

## First-party reference-suite smoke check

The four deployment-ready A2A `message/send` routes were exercised through the local Cloudflare Pages runtime:

- rebalancing returned a USD 500 bounded notional for a five-point drift;
- grid planning returned a 2.6388% level spacing against a 0.5% supplied round-trip fee;
- yield comparison ranked only the two caller-supplied APR observations and preserved the allocation cap;
- health-factor monitoring rejected a stressed 0.9143 health factor and calculated a USD 188 minimum repayment for the supplied target.

All responses declared read-only, no-custody, and no-trading controls. These local service checks do not constitute ERC-8004 registration.

## Public deployment check

- A new, isolated Cloudflare Pages project named `fourproof-bnb` was created without a custom domain, DNS change, route change, or modification to an existing Worker or Pages service.
- Both `https://fourproof-bnb.pages.dev` and the immutable deployment URL returned HTTP 200.
- The four public AgentCards and A2A `message/send` routes returned the same bounded results as the local suite.
- Browser QA loaded all four live categories with 15 ranked identities, 0 operational identities, and 15 safely blocked identities at the observed refresh.
- A fresh read-only `ownerOf` verification for ERC-8004 token `269223` matched the indexed owner at BSC block `118775727`.
- The activation-plan button remained disabled because discovery-domain ownership and the execution target were not independently validated.

The deployment did not connect a wallet, publish a custom domain, send a transaction, register an ERC-8004 identity, accept contest terms, or submit an entry.

## Remaining acceptance gate

Before a truthful contest submission, FourProof still needs applicant-owned wallet/registration decisions, participation-terms acceptance, a demo recording, and final submission. Any claim that an agent is operational still requires a reproducible, non-financial execution-target check; the current live marketplace intentionally reports zero operational third-party agents.
