import asyncio

from app.models import MissionRecord
from app.queue import pubsub_topic_path
from app.store import InMemoryMissionStore


def test_concurrent_delivery_gets_one_execution_lease() -> None:
    async def scenario() -> tuple[list[bool], MissionRecord | None]:
        store = InMemoryMissionStore()
        record = MissionRecord(
            mission_id="lease-test",
            target_url="https://example.com/agent.json",
            objective="Review this external agent under the enterprise onboarding policy.",
        )
        await store.create(record)
        claims = await asyncio.gather(store.claim(record.mission_id), store.claim(record.mission_id))
        return claims, await store.get(record.mission_id)

    claims, stored = asyncio.run(scenario())
    assert sorted(claims) == [False, True]
    assert stored is not None
    assert stored.attempt_count == 1
    assert stored.lease_expires_at is not None


def test_pubsub_short_topic_is_qualified_with_project(monkeypatch) -> None:
    monkeypatch.setenv("PUBSUB_TOPIC", "fourproof-missions")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fleet-demo-project")
    assert pubsub_topic_path() == "projects/fleet-demo-project/topics/fourproof-missions"


def test_pubsub_fully_qualified_topic_is_preserved(monkeypatch) -> None:
    path = "projects/fleet-demo-project/topics/fourproof-missions"
    monkeypatch.setenv("PUBSUB_TOPIC", path)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert pubsub_topic_path() == path
