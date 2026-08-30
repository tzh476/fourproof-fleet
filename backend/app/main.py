from __future__ import annotations

import base64
from collections import deque
import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .fixtures import fixture_for
from .models import MissionEvent, MissionRecord, MissionRequest
from .orchestrator import deterministic_demo, gemini_adk_run
from .queue import publish_mission, pubsub_topic, verify_pubsub_oidc
from .store import MissionStore, get_store


app = FastAPI(title="FourProof Fleet", version=__version__)
logger = logging.getLogger("fourproof_fleet")
logger.setLevel(logging.INFO)
if not logger.handlers:
    structured_handler = logging.StreamHandler()
    structured_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(structured_handler)
logger.propagate = False
mission_window: deque[float] = deque()
mission_window_lock = asyncio.Lock()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173").split(",") if origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'self' https://bsc-dataseed.bnbchain.org; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    )
    return response


def has_gemini_auth() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or (os.getenv("GOOGLE_CLOUD_PROJECT") and os.getenv("GOOGLE_GENAI_USE_VERTEXAI") == "TRUE"))


def live_target_allowed(target_url: str) -> bool:
    configured = {host.strip().lower() for host in os.getenv("ALLOWED_LIVE_HOSTS", "").split(",") if host.strip()}
    return not configured or (urlsplit(target_url).hostname or "").lower() in configured


async def reserve_mission_budget() -> None:
    limit = max(1, int(os.getenv("MISSION_LIMIT_PER_HOUR", "60")))
    cutoff = monotonic() - 3600
    async with mission_window_lock:
        while mission_window and mission_window[0] < cutoff:
            mission_window.popleft()
        if len(mission_window) >= limit:
            raise HTTPException(status_code=429, detail="public mission budget exhausted; retry after the rolling window")
        mission_window.append(monotonic())


def public_runtime_error(error: Exception) -> str:
    message = str(error)[:600]
    message = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[redacted-google-key]", message)
    message = re.sub(r"(?i)(bearer|token|api[_ -]?key|secret)(\s*[:=]\s*)\S+", r"\1\2[redacted]", message)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


async def run_mission(mission_id: str, request: MissionRequest, store: MissionStore) -> bool:
    if not await store.claim(mission_id):
        return False

    async def emit(event: MissionEvent) -> None:
        await store.append_event(mission_id, event)
        logger.info(
            json.dumps(
                {
                    "event": "mission_stage",
                    "mission_id": mission_id,
                    "sequence": event.sequence,
                    "stage": event.stage,
                    "status": event.status,
                    "title": event.title,
                },
                separators=(",", ":"),
            )
        )

    try:
        if request.demo_case:
            verdict = await deterministic_demo(request, emit)
        elif has_gemini_auth():
            verdict = await gemini_adk_run(request, mission_id, emit)
        else:
            verdict = await deterministic_demo(request, emit)
        await emit(MissionEvent(sequence=10, stage="receipt", status="completed", title="Evidence receipt sealed", detail=f"SHA-256 {verdict.receipt_sha256[:16]}… binds the verdict to its evidence set."))
        await store.finish(mission_id, verdict)
    except Exception as error:
        safe_error = public_runtime_error(error)
        logger.error(
            json.dumps(
                {"event": "mission_failed", "mission_id": mission_id, "error_type": type(error).__name__},
                separators=(",", ":"),
            )
        )
        try:
            await emit(MissionEvent(sequence=99, stage="runtime", status="failed", title="Mission failed closed", detail=safe_error))
        finally:
            await store.fail(mission_id, safe_error)
    return True


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "service": "fourproof-fleet",
        "version": __version__,
        "model": "gemini-3.5-flash",
        "googleAdk": "2.8.0",
        "geminiConfigured": has_gemini_auth(),
        "store": "firestore" if os.getenv("FIRESTORE_ENABLED") == "1" else "memory",
        "queue": "pubsub" if pubsub_topic() else "in-process",
        "runtime": "google-cloud-run" if os.getenv("K_SERVICE") else "local",
        "observability": "adk-opentelemetry+structured-cloud-logging",
        "gitSha": os.getenv("APP_GIT_SHA", "uncommitted-local"),
        "missionLimitPerHourPerInstance": max(1, int(os.getenv("MISSION_LIMIT_PER_HOUR", "60"))),
        "liveTargetPolicy": "allowlist" if os.getenv("ALLOWED_LIVE_HOSTS", "").strip() else "any-public-host",
    }


@app.get("/api/fixtures/{case}")
async def fixture(case: str) -> dict[str, object]:
    try:
        return fixture_for(case)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/8004scan/{path:path}")
async def proxy_8004scan(path: str, request: Request) -> Response:
    if path != "agents" and not re.fullmatch(r"agents/56/\d+", path):
        raise HTTPException(status_code=404, detail="unsupported 8004scan route")
    query: dict[str, str] = {}
    if request.query_params.get("chain_id") is not None:
        query["chain_id"] = "56"
    search = (request.query_params.get("search") or "").strip()[:80]
    if search:
        query["search"] = search
    try:
        requested_limit = int(request.query_params.get("limit", "12"))
    except ValueError:
        requested_limit = 12
    query["limit"] = str(min(20, max(1, requested_limit)))
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            upstream = await client.get(
                f"https://api.8004scan.io/api/v1/{path}",
                params=query,
                headers={"Accept": "application/json", "User-Agent": "FourProof-Fleet/0.1"},
            )
    except httpx.HTTPError as error:
        logger.warning(json.dumps({"event": "registry_upstream_failed", "error_type": type(error).__name__}))
        raise HTTPException(status_code=502, detail="live registry upstream is temporarily unavailable") from error
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json").split(";", 1)[0],
        headers={"Cache-Control": "public, max-age=20, s-maxage=60", "X-Content-Type-Options": "nosniff"},
    )


async def enqueue_mission(
    request: MissionRequest,
    background: BackgroundTasks,
    *,
    previous_mission_id: str | None = None,
) -> MissionRecord:
    if not has_gemini_auth() and not request.demo_case:
        raise HTTPException(status_code=503, detail="Gemini is not configured; select an explicit demo fixture or configure Google credentials.")
    if request.demo_case is None and not live_target_allowed(str(request.target_url)):
        raise HTTPException(status_code=403, detail="live target is outside the deployed allowlist")
    await reserve_mission_budget()
    mission_id = uuid.uuid4().hex
    store = get_store()
    uses_gemini = has_gemini_auth() and request.demo_case is None
    record = MissionRecord(
        mission_id=mission_id,
        target_url=str(request.target_url),
        objective=request.objective,
        demo_case=request.demo_case,
        review_after_days=request.review_after_days,
        previous_mission_id=previous_mission_id,
        runtime={
            "model": "gemini-3.5-flash" if uses_gemini else "not-invoked",
            "framework": "Google ADK 2.8.0" if uses_gemini else "deterministic demo",
            "store": "firestore" if os.getenv("FIRESTORE_ENABLED") == "1" else "memory",
        },
        events=[
            MissionEvent(
                sequence=1,
                stage="intake",
                status="queued",
                title="Mission accepted",
                detail=(
                    f"Linked re-review of mission {previous_mission_id[:8]}; no external tool has been invoked yet."
                    if previous_mission_id
                    else "Target normalized; no external tool has been trusted or invoked yet."
                ),
            )
        ],
    )
    await store.create(record)
    if pubsub_topic():
        try:
            await publish_mission(mission_id)
        except Exception as error:
            await store.fail(mission_id, f"Pub/Sub publish failed closed: {public_runtime_error(error)}")
            raise HTTPException(status_code=503, detail="mission queue unavailable") from error
    else:
        background.add_task(run_mission, mission_id, request, store)
    return record


@app.post("/api/missions", status_code=202, response_model=MissionRecord)
async def create_mission(request: MissionRequest, background: BackgroundTasks) -> MissionRecord:
    return await enqueue_mission(request, background)


@app.post("/api/missions/{mission_id}/recheck", status_code=202, response_model=MissionRecord)
async def recheck_mission(mission_id: str, background: BackgroundTasks) -> MissionRecord:
    previous = await get_store().get(mission_id)
    if not previous:
        raise HTTPException(status_code=404, detail="mission not found")
    if previous.status not in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="mission must be terminal before it can be re-reviewed")
    request = MissionRequest(
        target_url=previous.target_url,
        objective=previous.objective,
        demo_case=previous.demo_case,
        review_after_days=previous.review_after_days,
    )
    return await enqueue_mission(request, background, previous_mission_id=mission_id)


@app.post("/api/internal/pubsub", status_code=204)
async def receive_pubsub(request: Request) -> Response:
    try:
        await verify_pubsub_oidc(request.headers.get("authorization"))
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    envelope = await request.json()
    try:
        encoded = envelope["message"]["data"]
        payload = json.loads(base64.b64decode(encoded, validate=True))
        mission_id = str(payload["mission_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="invalid Pub/Sub envelope") from error
    store = get_store()
    record = await store.get(mission_id)
    if not record:
        raise HTTPException(status_code=404, detail="mission not found")
    if record.status in {"completed", "failed"}:
        return Response(status_code=204)
    mission_request = MissionRequest(
        target_url=record.target_url,
        objective=record.objective,
        demo_case=record.demo_case,
        review_after_days=record.review_after_days,
    )
    executed = await run_mission(mission_id, mission_request, store)
    if not executed:
        latest = await store.get(mission_id)
        if latest and latest.status in {"completed", "failed"}:
            return Response(status_code=204)
        raise HTTPException(status_code=409, detail="mission execution already leased; retry later")
    return Response(status_code=204)


@app.get("/api/missions/{mission_id}", response_model=MissionRecord)
async def get_mission(mission_id: str) -> MissionRecord:
    record = await get_store().get(mission_id)
    if not record:
        raise HTTPException(status_code=404, detail="mission not found")
    return record


STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parents[2] / "dist"))
if STATIC_DIR.exists():
    assets = STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        candidate = (STATIC_DIR / path).resolve()
        if path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
