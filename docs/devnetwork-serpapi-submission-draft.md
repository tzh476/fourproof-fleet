# DevNetwork SerpApi submission draft

Status: **local draft only**. No DevNetwork registration, SerpApi account,
credentialed API call, video publication, submission, award, or payment is
claimed.

## Target challenge

**SerpApi – Best AI Use Case** at DevNetwork API + Cloud + AI Hackathon 2026.

## Project name

**FourProof SearchSeal**

## One-line pitch

FourProof SearchSeal stops an enterprise AI agent at the onboarding gate,
cross-checks its self-published AgentCard against bounded live search evidence,
and seals the exact evidence set to a reproducible SHA-256 decision receipt.

## Problem

An AgentCard is useful discovery metadata, but it is still authored by the
party asking for access. Operations teams need current public context without
turning an LLM into an unrestricted browser or silently upgrading search
snippets into verified identity.

## Solution

The existing FourProof Fleet workflow already binds one immutable AgentCard
snapshot, runs independent Google ADK reviewers, applies code-enforced safety
invariants, and stores a durable decision receipt. The SerpApi adaptation adds
a second, independently hashed evidence packet:

1. derive a bounded `site:<target-host>` query;
2. call the SerpApi Google Search API;
3. admit at most three sanitized HTTP(S) organic results;
4. treat every title and snippet as untrusted evidence, never instructions;
5. seal the sanitized search-packet hash beside the AgentCard hash;
6. persist typed provenance with provider, observation, and hash;
7. fail closed if SerpApi is configured but unavailable.

SerpApi is therefore central to the live-evidence claim rather than a cosmetic
search box. When the credential is absent, the original AgentCard-only path is
preserved and the product does not claim search-backed evidence.

## What is implemented

- isolated branch: `codex/devnetwork-serpapi-evidence`
- draft PR: <https://github.com/tzh476/fourproof-fleet/pull/1>
- bounded SerpApi client with credential-redacted application errors
- deterministic sanitization and SHA-256 sealing
- typed `agent-card` and `serpapi-search` provenance
- optional health disclosure through `serpApiConfigured`
- fail-closed behavior for configured upstream failures
- 48 backend tests, 13 frontend tests, Python compile check, and production build

## Required proof before this text becomes submission-ready

- Applicant reviews and accepts the DevNetwork and SerpApi account terms.
- A real `SERPAPI_API_KEY` is injected from a secret manager, never committed.
- One bounded live mission returns real organic results and two evidence hashes.
- The mission survives the existing AgentCard, prompt-injection, SSRF, model,
  Firestore, Pub/Sub, and receipt checks.
- The deployed Git SHA, public repository branch or merge commit, video, and
  Devpost text all match.
- The demo states the credential boundary accurately: SerpApi requires the key
  as an HTTPS URL parameter; FourProof does not copy it into application logs,
  model prompts, mission records, or receipts.

## Three-minute demo outline

**0:00–0:25 — The trust gap**

Show one self-published AgentCard and explain why metadata alone cannot approve
production access.

**0:25–0:55 — Two-source architecture**

Show the target-host query, SerpApi boundary, sanitized result cap, immutable
AgentCard snapshot, and the two independent hashes entering the receipt.

**0:55–1:35 — Live mission**

Launch one non-fixture mission. Show Cloud Run accepting it, Pub/Sub delivering
it, Firestore persisting the stages, and SerpApi returning the bounded evidence
packet without exposing the credential.

**1:35–2:10 — Independent reviewers**

Show Registry Scout, Identity Verifier, and Tool Guard fan out under Google ADK,
then the policy judge fan in. Emphasize that search text is untrusted data and
cannot issue tool instructions.

**2:10–2:40 — Fail closed**

Show a poisoned or contradictory target being quarantined by deterministic
runtime policy even if model prose is optimistic.

**2:40–3:00 — Receipt and value**

Show the AgentCard hash, SerpApi evidence hash, evidence-set hash, and final
receipt. Close with the operational value: current public context without an
unbounded browser and without confusing search visibility with verified
identity.

## Truthful Devpost technology list

SerpApi Google Search API, Gemini 3.5 Flash, Google Agent Development Kit,
Cloud Run, Firestore, Pub/Sub, Cloud Logging, FastAPI, Pydantic, React,
TypeScript, and Vite.

## Accounting boundary

This draft, its code branch, tests, PR, advertised prize, future registration,
and any eventual submission all count as USD 0 unless an official award or
received payment is independently verified.
