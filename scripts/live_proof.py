#!/usr/bin/env python3
"""Capture fail-closed, sanitized proof from an authorized live GCP deployment.

This script performs real Gemini missions and therefore requires an explicit
action-time acknowledgement in FOURPROOF_LIVE_PROOF_ACK. It never enables APIs,
changes IAM, deploys a revision, or prints access tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ACK_VALUE = "I_CONFIRM_USER_AUTHORIZED_GCP_AND_GEMINI_USAGE"
REQUIRED_APIS = {
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ProofError(RuntimeError):
    """Raised when observed cloud evidence does not satisfy a proof invariant."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_health(payload: dict[str, Any], expected_git_sha: str, expected_live_mission_limit: int) -> None:
    expected = {
        "ok": True,
        "runtime": "google-cloud-run",
        "store": "firestore",
        "queue": "pubsub",
        "geminiConfigured": True,
        "model": "gemini-3.5-flash",
        "googleAdk": "2.8.0",
        "liveTargetPolicy": "allowlist",
        "gitSha": expected_git_sha,
        "liveMissionTotalLimit": expected_live_mission_limit,
        "maxLlmCallsPerMission": 8,
        "maxOutputTokensPerCall": 2_048,
    }
    mismatches = {
        key: {"expected": value, "observed": payload.get(key)}
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise ProofError(f"/health did not prove the expected runtime: {json.dumps(mismatches, sort_keys=True)}")


def validate_mission(record: dict[str, Any], case: str) -> None:
    if record.get("status") != "completed":
        raise ProofError(f"{case} mission is not completed: {record.get('status')}")
    if record.get("demo_case") is not None:
        raise ProofError(f"{case} mission used a deterministic demo_case")
    runtime = record.get("runtime") or {}
    if runtime.get("model") != "gemini-3.5-flash" or runtime.get("store") != "firestore":
        raise ProofError(f"{case} mission runtime does not prove Gemini plus Firestore")
    if runtime.get("framework") != "Google ADK 2.8.0":
        raise ProofError(f"{case} mission did not report the expected Google ADK runtime")
    verdict = record.get("verdict") or {}
    if verdict.get("engine") != "gemini_adk":
        raise ProofError(f"{case} mission did not use engine=gemini_adk")
    expected_actions = {"poisoned": {"quarantine"}, "safe": {"human_review", "allow_sandbox"}}
    if verdict.get("action") not in expected_actions[case]:
        raise ProofError(f"{case} mission has unsafe or unexpected action: {verdict.get('action')}")
    hashes = verdict.get("evidence_sha256") or []
    if not hashes or any(not isinstance(value, str) or not SHA256_RE.fullmatch(value) for value in hashes):
        raise ProofError(f"{case} mission is missing exact evidence hashes")
    if verdict.get("evidence_set_sha256") != canonical_sha256(sorted(set(hashes))):
        raise ProofError(f"{case} mission evidence-set hash is not reproducible")
    if not SHA256_RE.fullmatch(str(verdict.get("receipt_sha256", ""))):
        raise ProofError(f"{case} mission is missing a sealed decision receipt")
    stages = {event.get("stage") for event in record.get("events") or []}
    if not {"intake", "runtime", "scout", "identity", "guard", "judge", "receipt"}.issubset(stages):
        raise ProofError(f"{case} mission is missing required lifecycle stages")
    if case == "poisoned" and not any(
        event.get("stage") == "guard" and event.get("status") == "blocked"
        for event in record.get("events") or []
    ):
        raise ProofError("poisoned mission did not record a blocked guard stage")


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request_headers = {"Accept": "application/json", "User-Agent": "FourProof-Live-Proof/0.1"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_000)
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read(4_000).decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"detail": raw}
        return error.code, detail
    except (urllib.error.URLError, TimeoutError) as error:
        raise ProofError(f"request failed for {url}: {type(error).__name__}") from error


def _gcloud_json(arguments: list[str]) -> Any:
    command = ["gcloud", *arguments, "--format=json", "--quiet"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()[-1_500:]
        raise ProofError(f"gcloud read failed ({' '.join(arguments[:3])}): {stderr}")
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as error:
        raise ProofError(f"gcloud returned invalid JSON for {' '.join(arguments[:3])}") from error


def _poll_mission(base_url: str, mission_id: str, deadline: float) -> dict[str, Any]:
    while time.monotonic() < deadline:
        status, record = _request_json(f"{base_url}/api/missions/{mission_id}")
        if status != 200:
            raise ProofError(f"mission {mission_id} lookup returned HTTP {status}")
        if record.get("status") in {"completed", "failed"}:
            return record
        time.sleep(2)
    raise ProofError(f"mission {mission_id} did not finish before the proof timeout")


def _launch_mission(base_url: str, case: str, timeout_seconds: int) -> dict[str, Any]:
    status, created = _request_json(
        f"{base_url}/api/missions",
        method="POST",
        payload={
            "target_url": f"{base_url}/agentcards/{case}.json",
            "objective": "Decide whether this external agent may enter an isolated enterprise sandbox.",
            "review_after_days": 30,
        },
    )
    if status != 202 or not created.get("mission_id"):
        raise ProofError(f"{case} mission creation failed with HTTP {status}: {created.get('detail', 'no detail')}")
    return _poll_mission(base_url, created["mission_id"], time.monotonic() + timeout_seconds)


def _firestore_document(project_id: str, collection: str, document_id: str) -> dict[str, Any]:
    token_process = subprocess.run(
        ["gcloud", "auth", "print-access-token"], check=False, capture_output=True, text=True
    )
    token = token_process.stdout.strip()
    if token_process.returncode != 0 or not token:
        raise ProofError("could not obtain a temporary gcloud access token for read-only Firestore proof")
    document_path = "/".join(urllib.parse.quote(part, safe="") for part in (collection, document_id))
    url = (
        f"https://firestore.googleapis.com/v1/projects/{urllib.parse.quote(project_id, safe='')}"
        f"/databases/(default)/documents/{document_path}"
    )
    status, document = _request_json(url, headers={"Authorization": f"Bearer {token}"})
    if status != 200:
        raise ProofError(f"Firestore did not return document {document_id}: HTTP {status}")
    return document


def _validate_firestore_mission(document: dict[str, Any], mission_id: str) -> None:
    fields = document.get("fields") or {}
    if (fields.get("mission_id") or {}).get("stringValue") != mission_id:
        raise ProofError(f"Firestore document did not contain the expected mission id {mission_id}")
    if (fields.get("status") or {}).get("stringValue") != "completed":
        raise ProofError(f"Firestore mission {mission_id} is not terminal")


def _validate_firestore_budget(
    document: dict[str, Any], expected_git_sha: str, expected_limit: int
) -> tuple[int, int]:
    fields = document.get("fields") or {}
    if (fields.get("kind") or {}).get("stringValue") != "live_mission_budget":
        raise ProofError("Firestore live budget document has the wrong kind")
    if (fields.get("budget_id") or {}).get("stringValue") != expected_git_sha:
        raise ProofError("Firestore live budget is not bound to the deployed Git SHA")
    try:
        used = int((fields.get("used") or {})["integerValue"])
        limit = int((fields.get("limit") or {})["integerValue"])
    except (KeyError, TypeError, ValueError) as error:
        raise ProofError("Firestore live budget is missing integer counters") from error
    if limit != expected_limit or used < 3 or used >= limit:
        raise ProofError(
            f"Firestore live budget is inconsistent or has no judging headroom: used={used}, limit={limit}"
        )
    return used, limit


def _logging_proof(project_id: str, mission_id: str, timeout_seconds: int = 60) -> list[dict[str, Any]]:
    query = (
        'resource.type="cloud_run_revision" AND '
        'jsonPayload.event="mission_stage" AND '
        f'jsonPayload.mission_id="{mission_id}"'
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        entries = _gcloud_json(
            ["logging", "read", query, "--project", project_id, "--freshness=2h", "--limit=100"]
        )
        if entries and any((entry.get("jsonPayload") or {}).get("stage") == "receipt" for entry in entries):
            return entries
        time.sleep(3)
    raise ProofError(f"Cloud Logging did not expose the receipt stage for mission {mission_id}")


def _summarize_mission(record: dict[str, Any]) -> dict[str, Any]:
    verdict = record["verdict"]
    return {
        "missionId": record["mission_id"],
        "previousMissionId": record.get("previous_mission_id"),
        "status": record["status"],
        "action": verdict["action"],
        "engine": verdict["engine"],
        "evidenceSetSha256": verdict["evidence_set_sha256"],
        "receiptSha256": verdict["receipt_sha256"],
        "attemptCount": record.get("attempt_count"),
        "nextReviewAt": record.get("next_review_at"),
        "eventStages": [event.get("stage") for event in record.get("events") or []],
    }


def capture(args: argparse.Namespace) -> dict[str, Any]:
    if os.getenv("FOURPROOF_LIVE_PROOF_ACK") != ACK_VALUE:
        raise ProofError(
            "live proof would invoke Gemini; set FOURPROOF_LIVE_PROOF_ACK only after action-time user authorization"
        )
    base_url = args.base_url.rstrip("/")
    parsed_url = urllib.parse.urlsplit(base_url)
    if parsed_url.scheme != "https" or not (parsed_url.hostname or "").endswith(".run.app"):
        raise ProofError("--base-url must be an HTTPS Cloud Run .run.app URL")
    if not GIT_SHA_RE.fullmatch(args.expected_git_sha):
        raise ProofError("--expected-git-sha must be the full 40-character Git SHA")
    if args.expected_live_mission_limit != 8:
        raise ProofError("--expected-live-mission-limit must be exactly 8")

    project = _gcloud_json(["projects", "describe", args.project_id])
    if project.get("lifecycleState") != "ACTIVE":
        raise ProofError("the selected Google Cloud project is not ACTIVE")
    billing = _gcloud_json(["billing", "projects", "describe", args.project_id])
    if billing.get("billingEnabled") is not True:
        raise ProofError("billing is not enabled for the selected Google Cloud project")
    enabled_services = {
        item.get("config", {}).get("name")
        for item in _gcloud_json(["services", "list", "--enabled", "--project", args.project_id])
    }
    missing_apis = sorted(REQUIRED_APIS - enabled_services)
    if missing_apis:
        raise ProofError(f"required APIs are not enabled: {', '.join(missing_apis)}")

    service = _gcloud_json(
        ["run", "services", "describe", args.service_name, "--region", args.region, "--project", args.project_id]
    )
    status = service.get("status") or {}
    if status.get("url") != base_url or status.get("latestReadyRevisionName") != status.get("latestCreatedRevisionName"):
        raise ProofError("Cloud Run service URL or ready revision does not match the requested deployment")
    ready = any(
        condition.get("type") == "Ready" and condition.get("status") == "True"
        for condition in status.get("conditions") or []
    )
    if not ready:
        raise ProofError("Cloud Run service does not have a Ready=True condition")

    subscription = _gcloud_json(
        ["pubsub", "subscriptions", "describe", args.subscription_name, "--project", args.project_id]
    )
    push = subscription.get("pushConfig") or {}
    oidc = push.get("oidcToken") or {}
    if push.get("pushEndpoint") != f"{base_url}/api/internal/pubsub":
        raise ProofError("Pub/Sub push endpoint does not match the Cloud Run mission endpoint")
    if oidc.get("audience") != base_url or oidc.get("serviceAccountEmail") != args.runtime_service_account:
        raise ProofError("Pub/Sub OIDC audience or service account does not match the deployment")

    health_status, health = _request_json(f"{base_url}/health")
    if health_status != 200:
        raise ProofError(f"/health returned HTTP {health_status}")
    validate_health(health, args.expected_git_sha, args.expected_live_mission_limit)

    forged_status, _ = _request_json(f"{base_url}/api/internal/pubsub", method="POST", payload={})
    if forged_status not in {401, 403}:
        raise ProofError(f"forged Pub/Sub push was not rejected: HTTP {forged_status}")

    poisoned = _launch_mission(base_url, "poisoned", args.timeout_seconds)
    safe = _launch_mission(base_url, "safe", args.timeout_seconds)
    validate_mission(poisoned, "poisoned")
    validate_mission(safe, "safe")

    recheck_status, recheck_created = _request_json(
        f"{base_url}/api/missions/{safe['mission_id']}/recheck", method="POST", payload={}
    )
    if recheck_status != 202 or not recheck_created.get("mission_id"):
        raise ProofError(f"linked recheck creation failed with HTTP {recheck_status}")
    safe_recheck = _poll_mission(
        base_url, recheck_created["mission_id"], time.monotonic() + args.timeout_seconds
    )
    validate_mission(safe_recheck, "safe")
    if safe_recheck.get("previous_mission_id") != safe["mission_id"]:
        raise ProofError("linked recheck did not preserve previous_mission_id")
    if safe_recheck["verdict"]["evidence_set_sha256"] != safe["verdict"]["evidence_set_sha256"]:
        raise ProofError("unchanged safe AgentCard did not preserve the stable evidence-set hash")

    for mission in (poisoned, safe, safe_recheck):
        document = _firestore_document(args.project_id, args.firestore_collection, mission["mission_id"])
        _validate_firestore_mission(document, mission["mission_id"])
    budget_document = _firestore_document(
        args.project_id, args.firestore_collection, f"_live_budget_{args.expected_git_sha}"
    )
    budget_used, budget_limit = _validate_firestore_budget(
        budget_document, args.expected_git_sha, args.expected_live_mission_limit
    )
    poison_logs = _logging_proof(args.project_id, poisoned["mission_id"])
    safe_logs = _logging_proof(args.project_id, safe["mission_id"])

    proof = {
        "schemaVersion": 1,
        "capturedAt": datetime.now(UTC).isoformat(),
        "source": "observed live Google Cloud state; no expected values were copied as observations",
        "service": {
            "url": base_url,
            "revision": status["latestReadyRevisionName"],
            "gitSha": health["gitSha"],
            "runtime": health["runtime"],
            "store": health["store"],
            "queue": health["queue"],
            "model": health["model"],
            "googleAdk": health["googleAdk"],
            "maxLlmCallsPerMission": health["maxLlmCallsPerMission"],
            "maxOutputTokensPerCall": health["maxOutputTokensPerCall"],
        },
        "infrastructure": {
            "requiredApisEnabled": True,
            "billingEnabledAtCapture": True,
            "firestoreDocumentsObserved": 3,
            "pubsubOidcVerified": True,
            "forgedPushStatus": forged_status,
            "cloudLoggingEntriesObserved": len(poison_logs) + len(safe_logs),
            "liveMissionBudget": {
                "usedAtCapture": budget_used,
                "limit": budget_limit,
                "remaining": budget_limit - budget_used,
                "boundToGitSha": True,
            },
        },
        "missions": {
            "poisoned": _summarize_mission(poisoned),
            "safe": _summarize_mission(safe),
            "safeRecheck": _summarize_mission(safe_recheck),
        },
    }
    return proof


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--base-url", required=True)
    result.add_argument("--project-id", required=True)
    result.add_argument("--region", required=True)
    result.add_argument("--service-name", required=True)
    result.add_argument("--runtime-service-account", required=True)
    result.add_argument("--expected-git-sha", required=True)
    result.add_argument("--expected-live-mission-limit", required=True, type=int)
    result.add_argument("--subscription-name", default="fourproof-missions-push")
    result.add_argument("--firestore-collection", default="fourproof_missions")
    result.add_argument("--timeout-seconds", type=int, default=300)
    result.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        proof = capture(args)
    except ProofError as error:
        print(f"LIVE PROOF FAILED: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(proof, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"LIVE PROOF PASSED: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
