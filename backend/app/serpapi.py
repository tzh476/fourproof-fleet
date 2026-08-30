from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

import httpx

from .safety import sha256_json


SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
MAX_RESULTS = 3


def serpapi_configured() -> bool:
    return bool(os.getenv("SERPAPI_API_KEY", "").strip())


def _public_result(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    link = str(item.get("link") or "").strip()
    parsed = urlsplit(link)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return {
        "title": str(item.get("title") or "")[:180],
        "link": link[:500],
        "displayed_link": str(item.get("displayed_link") or "")[:180],
        "snippet": str(item.get("snippet") or "")[:500],
    }


async def search_public_evidence(
    target_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Fetch a bounded, sanitized SerpApi evidence packet for the target host.

    The API credential is used only in the upstream request. It is never included
    in the returned packet, logs, mission events, hashes, or public error text.
    """
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return None
    hostname = (urlsplit(target_url).hostname or "").lower()
    if not hostname:
        raise RuntimeError("SerpApi evidence requires a target hostname")
    query = f'site:{hostname} (agent OR API OR documentation OR security)'
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=8.0, follow_redirects=False)
    try:
        try:
            response = await active_client.get(
                SERPAPI_ENDPOINT,
                params={
                    "engine": "google",
                    "q": query,
                    "num": str(MAX_RESULTS),
                    "api_key": api_key,
                },
                headers={"Accept": "application/json", "User-Agent": "FourProof-Fleet/0.2"},
            )
        except httpx.HTTPError as error:
            raise RuntimeError("SerpApi evidence request failed") from error
        if response.status_code != 200:
            raise RuntimeError("SerpApi evidence source returned a non-success status")
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError("SerpApi evidence source returned invalid JSON") from error
    finally:
        if owns_client:
            await active_client.aclose()
    raw_results = payload.get("organic_results") if isinstance(payload, dict) else None
    results = [result for item in (raw_results or []) if (result := _public_result(item))][:MAX_RESULTS]
    evidence = {
        "provider": "SerpApi Google Search API",
        "query": query,
        "target_host": hostname,
        "result_count": len(results),
        "results": results,
    }
    return {"evidence": evidence, "sha256": sha256_json(evidence)}
