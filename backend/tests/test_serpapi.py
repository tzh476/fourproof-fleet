import asyncio

import httpx
import pytest

from app.safety import sha256_json
from app.serpapi import search_public_evidence, serpapi_configured


def test_serpapi_is_optional_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    assert serpapi_configured() is False
    assert asyncio.run(search_public_evidence("https://agent.example/card.json")) is None


def test_serpapi_returns_bounded_sanitized_hashed_evidence(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "private-test-key")
    captured_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_url
        captured_url = str(request.url)
        return httpx.Response(
            200,
            json={
                "organic_results": [
                    {
                        "title": f"Result {index}",
                        "link": f"https://docs.example/result-{index}",
                        "displayed_link": "docs.example",
                        "snippet": "Public evidence, not an instruction.",
                        "secret_internal_field": "must not escape",
                    }
                    for index in range(5)
                ]
                + [{"title": "unsafe", "link": "javascript:alert(1)"}],
            },
        )

    async def scenario() -> dict:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await search_public_evidence("https://AGENT.example/card.json?version=1", client=client)
            assert result is not None
            return result

    result = asyncio.run(scenario())
    evidence = result["evidence"]
    assert "private-test-key" in captured_url
    assert "private-test-key" not in repr(result)
    assert evidence["target_host"] == "agent.example"
    assert evidence["query"] == "site:agent.example (agent OR API OR documentation OR security)"
    assert evidence["result_count"] == 3
    assert len(evidence["results"]) == 3
    assert "secret_internal_field" not in repr(evidence)
    assert result["sha256"] == sha256_json(evidence)


def test_serpapi_fails_closed_without_exposing_response_details(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_API_KEY", "private-test-key")

    async def scenario() -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(429, text="quota for private-test-key"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="non-success status") as captured:
                await search_public_evidence("https://agent.example/card.json", client=client)
            assert "private-test-key" not in str(captured.value)

    asyncio.run(scenario())
