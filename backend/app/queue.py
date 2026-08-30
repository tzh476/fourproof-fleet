from __future__ import annotations

import asyncio
import json
import os

from google.auth.transport import requests as google_requests
from google.cloud import pubsub_v1
from google.oauth2 import id_token


def pubsub_topic() -> str | None:
    value = os.getenv("PUBSUB_TOPIC", "").strip()
    return value or None


def pubsub_topic_path() -> str:
    topic = pubsub_topic()
    if not topic:
        raise RuntimeError("PUBSUB_TOPIC is not configured")
    if topic.startswith("projects/") and "/topics/" in topic:
        return topic
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required when PUBSUB_TOPIC is not fully qualified")
    return f"projects/{project_id}/topics/{topic}"


async def publish_mission(mission_id: str) -> str:
    topic = pubsub_topic_path()

    def _publish() -> str:
        publisher = pubsub_v1.PublisherClient()
        future = publisher.publish(topic, json.dumps({"mission_id": mission_id}).encode("utf-8"), event_type="mission.created")
        return future.result(timeout=12)

    return await asyncio.to_thread(_publish)


async def verify_pubsub_oidc(authorization: str | None) -> dict[str, object]:
    audience = os.getenv("PUBSUB_AUDIENCE", "").strip()
    expected_email = os.getenv("PUBSUB_SERVICE_ACCOUNT_EMAIL", "").strip()
    if not audience or not expected_email:
        raise RuntimeError("PUBSUB_AUDIENCE and PUBSUB_SERVICE_ACCOUNT_EMAIL must be configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise PermissionError("missing Pub/Sub OIDC bearer token")
    token = authorization.removeprefix("Bearer ").strip()

    def _verify() -> dict[str, object]:
        claims = id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)
        if claims.get("email") != expected_email or claims.get("email_verified") is not True:
            raise PermissionError("Pub/Sub service-account identity does not match")
        return claims

    return await asyncio.to_thread(_verify)
