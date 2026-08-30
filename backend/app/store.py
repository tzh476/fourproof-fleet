from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from .models import MissionEvent, MissionRecord, MissionStatus, MissionVerdict, utc_now


class MissionStore(ABC):
    @abstractmethod
    async def create(self, record: MissionRecord) -> MissionRecord: ...

    @abstractmethod
    async def get(self, mission_id: str) -> MissionRecord | None: ...

    @abstractmethod
    async def reserve_live_budget(self, budget_id: str, limit: int) -> int | None: ...

    @abstractmethod
    async def claim(self, mission_id: str, *, lease_seconds: int = 360) -> bool: ...

    @abstractmethod
    async def append_event(self, mission_id: str, event: MissionEvent) -> MissionRecord: ...

    @abstractmethod
    async def finish(self, mission_id: str, verdict: MissionVerdict) -> MissionRecord: ...

    @abstractmethod
    async def fail(self, mission_id: str, error: str) -> MissionRecord: ...


class InMemoryMissionStore(MissionStore):
    def __init__(self) -> None:
        self._records: dict[str, MissionRecord] = {}
        self._live_budgets: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: MissionRecord) -> MissionRecord:
        async with self._lock:
            self._records[record.mission_id] = record.model_copy(deep=True)
            return record.model_copy(deep=True)

    async def get(self, mission_id: str) -> MissionRecord | None:
        async with self._lock:
            record = self._records.get(mission_id)
            return record.model_copy(deep=True) if record else None

    async def reserve_live_budget(self, budget_id: str, limit: int) -> int | None:
        async with self._lock:
            used = self._live_budgets.get(budget_id, 0)
            if used >= limit:
                return None
            used += 1
            self._live_budgets[budget_id] = used
            return used

    async def claim(self, mission_id: str, *, lease_seconds: int = 360) -> bool:
        async with self._lock:
            record = self._records.get(mission_id)
            if not record or record.status in {MissionStatus.COMPLETED, MissionStatus.FAILED}:
                return False
            now = datetime.now(UTC)
            if record.status == MissionStatus.RUNNING and record.lease_expires_at:
                if datetime.fromisoformat(record.lease_expires_at) > now:
                    return False
            record.status = MissionStatus.RUNNING
            record.attempt_count += 1
            record.lease_expires_at = (now + timedelta(seconds=lease_seconds)).isoformat()
            record.updated_at = now.isoformat()
            return True

    async def append_event(self, mission_id: str, event: MissionEvent) -> MissionRecord:
        async with self._lock:
            record = self._records[mission_id]
            record.events.append(event)
            record.updated_at = utc_now()
            if event.status == "running":
                record.status = MissionStatus.RUNNING
            return record.model_copy(deep=True)

    async def finish(self, mission_id: str, verdict: MissionVerdict) -> MissionRecord:
        async with self._lock:
            record = self._records[mission_id]
            record.verdict = verdict
            record.status = MissionStatus.COMPLETED
            record.lease_expires_at = None
            completed_at = datetime.now(UTC)
            record.updated_at = completed_at.isoformat()
            record.next_review_at = (completed_at + timedelta(days=record.review_after_days)).isoformat()
            return record.model_copy(deep=True)

    async def fail(self, mission_id: str, error: str) -> MissionRecord:
        async with self._lock:
            record = self._records[mission_id]
            record.error = error
            record.status = MissionStatus.FAILED
            record.lease_expires_at = None
            record.updated_at = utc_now()
            return record.model_copy(deep=True)


class FirestoreMissionStore(MissionStore):
    def __init__(self) -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self._client = firestore.AsyncClient()
        self._collection = self._client.collection(os.getenv("FIRESTORE_COLLECTION", "fourproof_missions"))

    async def create(self, record: MissionRecord) -> MissionRecord:
        await self._collection.document(record.mission_id).set(record.model_dump(mode="json"))
        return record

    async def get(self, mission_id: str) -> MissionRecord | None:
        snapshot = await self._collection.document(mission_id).get()
        return MissionRecord.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def reserve_live_budget(self, budget_id: str, limit: int) -> int | None:
        document = self._collection.document(f"_live_budget_{budget_id}")
        transaction = self._client.transaction()

        @self._firestore.async_transactional
        async def reserve_in_transaction(current_transaction) -> int | None:
            snapshot = await document.get(transaction=current_transaction)
            state = snapshot.to_dict() if snapshot.exists else {}
            used = int((state or {}).get("used", 0))
            if used >= limit:
                return None
            used += 1
            current_transaction.set(
                document,
                {
                    "kind": "live_mission_budget",
                    "budget_id": budget_id,
                    "used": used,
                    "limit": limit,
                    "updated_at": utc_now(),
                },
            )
            return used

        return await reserve_in_transaction(transaction)

    async def claim(self, mission_id: str, *, lease_seconds: int = 360) -> bool:
        document = self._collection.document(mission_id)
        transaction = self._client.transaction()

        @self._firestore.async_transactional
        async def claim_in_transaction(current_transaction) -> bool:
            snapshot = await document.get(transaction=current_transaction)
            if not snapshot.exists:
                return False
            record = MissionRecord.model_validate(snapshot.to_dict())
            if record.status in {MissionStatus.COMPLETED, MissionStatus.FAILED}:
                return False
            now = datetime.now(UTC)
            if record.status == MissionStatus.RUNNING and record.lease_expires_at:
                if datetime.fromisoformat(record.lease_expires_at) > now:
                    return False
            current_transaction.update(
                document,
                {
                    "status": MissionStatus.RUNNING.value,
                    "attempt_count": record.attempt_count + 1,
                    "lease_expires_at": (now + timedelta(seconds=lease_seconds)).isoformat(),
                    "updated_at": now.isoformat(),
                },
            )
            return True

        return await claim_in_transaction(transaction)

    async def _replace(self, record: MissionRecord) -> MissionRecord:
        await self._collection.document(record.mission_id).set(record.model_dump(mode="json"))
        return record

    async def append_event(self, mission_id: str, event: MissionEvent) -> MissionRecord:
        record = await self.get(mission_id)
        if not record:
            raise KeyError(mission_id)
        record.events.append(event)
        record.updated_at = utc_now()
        if event.status == "running":
            record.status = MissionStatus.RUNNING
        return await self._replace(record)

    async def finish(self, mission_id: str, verdict: MissionVerdict) -> MissionRecord:
        record = await self.get(mission_id)
        if not record:
            raise KeyError(mission_id)
        record.verdict = verdict
        record.status = MissionStatus.COMPLETED
        record.lease_expires_at = None
        completed_at = datetime.now(UTC)
        record.updated_at = completed_at.isoformat()
        record.next_review_at = (completed_at + timedelta(days=record.review_after_days)).isoformat()
        return await self._replace(record)

    async def fail(self, mission_id: str, error: str) -> MissionRecord:
        record = await self.get(mission_id)
        if not record:
            raise KeyError(mission_id)
        record.error = error
        record.status = MissionStatus.FAILED
        record.lease_expires_at = None
        record.updated_at = utc_now()
        return await self._replace(record)


@lru_cache(maxsize=1)
def get_store() -> MissionStore:
    if os.getenv("FIRESTORE_ENABLED") == "1":
        return FirestoreMissionStore()
    return InMemoryMissionStore()
