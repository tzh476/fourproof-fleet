import asyncio

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.fixtures import POISONED_AGENT_CARD
from app.main import app, live_target_allowed, mission_windows, public_runtime_error, reserve_mission_budget
from app.safety import sha256_json
from app.store import InMemoryMissionStore


client = TestClient(app)


def test_health_discloses_when_gemini_is_not_configured() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "gemini-3.5-flash"
    assert payload["googleAdk"] == "2.8.0"
    assert payload["geminiConfigured"] is False
    assert payload["liveMissionTotalLimit"] == 0
    assert payload["maxLlmCallsPerMission"] == 8
    assert payload["maxOutputTokensPerCall"] == 2_048


def test_poisoned_demo_is_quarantined_with_receipt() -> None:
    response = client.post(
        "/api/missions",
        json={
            "target_url": "https://demo.fourproof.invalid/poisoned",
            "demo_case": "poisoned",
            "objective": "Decide whether this agent may enter an isolated enterprise sandbox.",
        },
    )
    assert response.status_code == 202
    mission_id = response.json()["mission_id"]
    result = client.get(f"/api/missions/{mission_id}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["verdict"]["action"] == "quarantine"
    assert payload["verdict"]["engine"] == "deterministic_demo"
    assert len(payload["verdict"]["receipt_sha256"]) == 64
    assert payload["verdict"]["evidence_sha256"] == [sha256_json(POISONED_AGENT_CARD)]
    assert payload["verdict"]["evidence_set_sha256"] == sha256_json(payload["verdict"]["evidence_sha256"])
    assert any(event["status"] == "blocked" for event in payload["events"])


def test_live_target_fails_closed_without_gemini_credentials() -> None:
    response = client.post(
        "/api/missions",
        json={
            "target_url": "https://example.com/.well-known/agent-card.json",
            "objective": "Review a live agent for enterprise onboarding with evidence.",
        },
    )
    assert response.status_code == 503


def test_live_total_budget_blocks_model_work_but_not_explicit_fixtures(monkeypatch) -> None:
    monkeypatch.setenv("MISSION_LIMIT_PER_HOUR", "20")
    monkeypatch.setenv("LIVE_MISSION_TOTAL_LIMIT", "2")
    monkeypatch.setenv("APP_GIT_SHA", "budget-test-commit")
    mission_windows["live"].clear()
    mission_windows["fixture"].clear()

    async def scenario() -> None:
        store = InMemoryMissionStore()
        await reserve_mission_budget(store, uses_gemini=True)
        await reserve_mission_budget(store, uses_gemini=True)
        with pytest.raises(HTTPException, match="exhausted its total live Gemini mission budget"):
            await reserve_mission_budget(store, uses_gemini=True)
        await reserve_mission_budget(store, uses_gemini=False)

    asyncio.run(scenario())


def test_explicit_demo_never_masquerades_as_gemini_when_key_exists(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-is-never-invoked")
    response = client.post(
        "/api/missions",
        json={
            "target_url": "https://demo.fourproof.invalid/safe",
            "demo_case": "safe",
            "objective": "Review a reproducible fixture without claiming a model invocation.",
        },
    )
    assert response.status_code == 202
    result = client.get(f"/api/missions/{response.json()['mission_id']}").json()
    assert result["verdict"]["engine"] == "deterministic_demo"
    assert result["runtime"]["model"] == "not-invoked"


def test_terminal_mission_can_create_linked_reproducible_review() -> None:
    first_response = client.post(
        "/api/missions",
        json={
            "target_url": "https://demo.fourproof.invalid/safe",
            "demo_case": "safe",
            "review_after_days": 30,
            "objective": "Preserve context for a linked enterprise lifecycle review.",
        },
    )
    first = client.get(f"/api/missions/{first_response.json()['mission_id']}").json()
    assert first["status"] == "completed"
    assert first["next_review_at"] is not None

    recheck_response = client.post(f"/api/missions/{first['mission_id']}/recheck")
    assert recheck_response.status_code == 202
    second = client.get(f"/api/missions/{recheck_response.json()['mission_id']}").json()
    assert second["previous_mission_id"] == first["mission_id"]
    assert second["status"] == "completed"
    assert second["verdict"]["evidence_set_sha256"] == first["verdict"]["evidence_set_sha256"]
    assert second["verdict"]["receipt_sha256"] == first["verdict"]["receipt_sha256"]


def test_registry_proxy_rejects_arbitrary_paths_without_upstream_call() -> None:
    response = client.get("/api/8004scan/admin/secrets")
    assert response.status_code == 404


def test_registry_proxy_turns_upstream_timeout_into_bounded_error(monkeypatch) -> None:
    async def raise_timeout(*args, **kwargs):
        raise httpx.ReadTimeout("bounded timeout")

    monkeypatch.setattr(httpx.AsyncClient, "get", raise_timeout)
    response = client.get("/api/8004scan/agents?chain_id=56&limit=12")
    assert response.status_code == 502
    assert response.json()["detail"] == "live registry upstream is temporarily unavailable"


def test_security_headers_are_applied() -> None:
    response = client.get("/healthz")
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_live_target_allowlist_is_exact(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_LIVE_HOSTS", "fleet.example.run.app")
    assert live_target_allowed("https://fleet.example.run.app/agentcards/safe.json") is True
    assert live_target_allowed("https://fleet.example.run.app.attacker.example/card.json") is False


def test_pubsub_push_requires_configured_oidc_identity() -> None:
    response = client.post("/api/internal/pubsub", json={"message": {"data": "e30="}})
    assert response.status_code == 503


def test_runtime_error_redacts_google_key_material() -> None:
    rendered = public_runtime_error(RuntimeError("request failed for api_key=AIza" + "a" * 35))
    assert "AIza" not in rendered
    assert "[redacted-google-key]" in rendered or "[redacted]" in rendered
