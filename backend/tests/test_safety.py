import asyncio

import httpx
import pytest

from app.fixtures import POISONED_AGENT_CARD, SAFE_AGENT_CARD
from app.safety import scan_prompt_injection, sha256_json, validate_public_http_url
from app.tools import (
    MAX_AGENT_CARD_BYTES,
    bind_agent_card_snapshot,
    decode_agent_card_response,
    fetch_agent_card,
    reset_agent_card_snapshot,
    inspect_tool_boundary,
)


def test_safe_card_has_no_prompt_injection_signals() -> None:
    assert scan_prompt_injection(SAFE_AGENT_CARD) == []


def test_poisoned_card_finds_multiple_independent_signals() -> None:
    signals = scan_prompt_injection(POISONED_AGENT_CARD)
    assert "instruction_override" in signals
    assert "secret_exfiltration" in signals
    assert "tool_coercion" in signals
    assert "role_impersonation" in signals


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.0.0.5/agent-card.json",
        "http://localhost/agent-card.json",
        "file:///etc/passwd",
        "https://user:password@example.com/card",
        "https://example.com/card?api_key=secret",
        "https://example.com/card#not-sent-to-server",
    ],
)
def test_public_url_policy_blocks_ssrf_and_credentials(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_http_url(url)


def test_receipt_hash_is_canonical() -> None:
    assert sha256_json({"b": 2, "a": 1}) == sha256_json({"a": 1, "b": 2})


def test_bound_snapshot_prevents_parallel_reviewers_from_refetching_mutable_input() -> None:
    snapshot = {
        "source": "https://example.com/original.json",
        "http_status": 200,
        "card": SAFE_AGENT_CARD,
        "sha256": sha256_json(SAFE_AGENT_CARD),
    }
    token = bind_agent_card_snapshot(snapshot)

    async def read_with_different_arguments() -> list[dict[str, object]]:
        return await asyncio.gather(
            fetch_agent_card("https://attacker.example/a.json"),
            fetch_agent_card("https://attacker.example/b.json"),
            fetch_agent_card("https://attacker.example/c.json"),
        )

    try:
        results = asyncio.run(read_with_different_arguments())
    finally:
        reset_agent_card_snapshot(token)
    assert {result["sha256"] for result in results} == {snapshot["sha256"]}
    assert all(result["source"] == snapshot["source"] for result in results)


def test_streaming_response_stops_after_decompressed_size_limit() -> None:
    request = httpx.Request("GET", "https://example.com/agent.json")
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        content=b'{' + b'"x":"' + b"a" * MAX_AGENT_CARD_BYTES + b'"}',
        request=request,
    )
    with pytest.raises(ValueError, match="256KB"):
        asyncio.run(decode_agent_card_response(response))


def test_streaming_response_rejects_non_object_json() -> None:
    request = httpx.Request("GET", "https://example.com/agent.json")
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        content=b"[]",
        request=request,
    )
    with pytest.raises(ValueError, match="root"):
        asyncio.run(decode_agent_card_response(response))


def test_live_evidence_hash_binds_exact_response_bytes() -> None:
    request = httpx.Request("GET", "https://example.com/agent.json")
    compact = httpx.Response(200, headers={"content-type": "application/json"}, content=b'{"x":1}', request=request)
    spaced = httpx.Response(200, headers={"content-type": "application/json"}, content=b'{ "x": 1 }', request=request)
    compact_card, compact_hash = asyncio.run(decode_agent_card_response(compact))
    spaced_card, spaced_hash = asyncio.run(decode_agent_card_response(spaced))
    assert compact_card == spaced_card
    assert compact_hash != spaced_hash


def test_safe_fixture_does_not_claim_an_unperformed_endpoint_probe() -> None:
    report = asyncio.run(inspect_tool_boundary("https://demo.fourproof.invalid/safe", "safe"))
    assert report["endpoint_state"] == "policy_passed"
