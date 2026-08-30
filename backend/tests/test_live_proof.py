import pytest

from scripts.live_proof import ProofError, canonical_sha256, validate_health, validate_mission


def healthy_runtime() -> dict:
    return {
        "ok": True,
        "runtime": "google-cloud-run",
        "store": "firestore",
        "queue": "pubsub",
        "geminiConfigured": True,
        "model": "gemini-3.5-flash",
        "googleAdk": "2.8.0",
        "liveTargetPolicy": "allowlist",
        "gitSha": "a" * 40,
    }


def live_mission(case: str) -> dict:
    evidence = ["b" * 64]
    return {
        "status": "completed",
        "demo_case": None,
        "runtime": {"model": "gemini-3.5-flash", "framework": "Google ADK 2.8.0", "store": "firestore"},
        "verdict": {
            "action": "quarantine" if case == "poisoned" else "human_review",
            "engine": "gemini_adk",
            "evidence_sha256": evidence,
            "evidence_set_sha256": canonical_sha256(evidence),
            "receipt_sha256": "c" * 64,
        },
        "events": [
            {"stage": "intake", "status": "queued"},
            {"stage": "runtime", "status": "running"},
            {"stage": "scout", "status": "completed"},
            {"stage": "identity", "status": "completed"},
            {"stage": "guard", "status": "blocked" if case == "poisoned" else "completed"},
            {"stage": "judge", "status": "completed"},
            {"stage": "receipt", "status": "completed"},
        ],
    }


def test_live_proof_accepts_exact_cloud_health_and_two_counterexamples() -> None:
    validate_health(healthy_runtime(), "a" * 40)
    validate_mission(live_mission("poisoned"), "poisoned")
    validate_mission(live_mission("safe"), "safe")


def test_live_proof_rejects_local_or_unversioned_runtime() -> None:
    payload = healthy_runtime()
    payload["runtime"] = "local"
    payload["gitSha"] = "uncommitted-local"
    with pytest.raises(ProofError, match="expected runtime"):
        validate_health(payload, "a" * 40)


def test_live_proof_rejects_deterministic_fixture_masquerading_as_gemini() -> None:
    record = live_mission("poisoned")
    record["demo_case"] = "poisoned"
    record["verdict"]["engine"] = "deterministic_demo"
    with pytest.raises(ProofError, match="deterministic demo_case"):
        validate_mission(record, "poisoned")


def test_live_proof_recomputes_the_stable_evidence_set_hash() -> None:
    record = live_mission("safe")
    record["verdict"]["evidence_set_sha256"] = "d" * 64
    with pytest.raises(ProofError, match="not reproducible"):
        validate_mission(record, "safe")
