from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from .safety import validate_public_http_url


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class MissionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MissionRequest(BaseModel):
    target_url: AnyHttpUrl
    objective: str = Field(
        default="Decide whether this external agent may enter an isolated enterprise sandbox.",
        min_length=12,
        max_length=600,
    )
    demo_case: Literal["safe", "poisoned"] | None = None
    review_after_days: int = Field(default=30, ge=1, le=90)

    @field_validator("target_url")
    @classmethod
    def reject_url_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        validate_public_http_url(str(value), resolve_dns=False)
        return value


class EvidenceItem(BaseModel):
    evidence_id: str = Field(max_length=80)
    source: str = Field(max_length=500)
    observed: str = Field(max_length=700)
    sha256: str | None = None


class ScoutReport(BaseModel):
    subject_name: str = Field(max_length=160)
    summary: str = Field(max_length=400)
    declared_capabilities: list[str] = Field(max_length=12)
    endpoints: list[str] = Field(max_length=4)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=2)


class IdentityReport(BaseModel):
    identity_state: Literal["verified", "declared", "missing", "contradicted"]
    owner: str | None = None
    registry: str | None = None
    token_id: str | None = None
    contradictions: list[str] = Field(max_length=4)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=2)


class GuardReport(BaseModel):
    injection_signals: list[str] = Field(max_length=8)
    endpoint_state: Literal["reachable", "policy_passed", "blocked", "unreachable", "missing"]
    endpoint_notes: list[str] = Field(max_length=6)
    data_exposure_risks: list[str] = Field(max_length=6)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=2)


class ScoutFinding(BaseModel):
    subject_name: str = Field(max_length=80)
    capability_count: int = Field(ge=0, le=12)
    endpoint_count: int = Field(ge=0, le=4)
    evidence_id: Literal["scout-card"] = "scout-card"


class IdentityFinding(BaseModel):
    identity_state: Literal["verified", "declared", "missing", "contradicted"]
    contradictions: list[str] = Field(max_length=2)
    evidence_id: Literal["identity-claim"] = "identity-claim"


class GuardFinding(BaseModel):
    injection_signals: list[str] = Field(max_length=8)
    endpoint_state: Literal["reachable", "policy_passed", "blocked", "unreachable", "missing"]
    evidence_id: Literal["guard-scan"] = "guard-scan"


class ModelVerdict(BaseModel):
    """Compact model-owned fields; hashes and engine are runtime-owned."""

    action: Literal["allow_sandbox", "human_review", "quarantine"]
    confidence: float = Field(ge=0, le=1)
    executive_summary: str = Field(max_length=280)
    rationale: list[str] = Field(min_length=1, max_length=3)
    required_controls: list[str] = Field(max_length=5)
    evidence_ids: list[Literal["scout-card", "identity-claim", "guard-scan"]] = Field(
        min_length=1, max_length=3
    )

    @field_validator("rationale", "required_controls", "evidence_ids", mode="before")
    @classmethod
    def normalize_single_model_string(cls, value: Any) -> Any:
        """Accept Gemini's occasional scalar form without weakening item validation."""
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        return value


class MissionVerdict(BaseModel):
    action: Literal["allow_sandbox", "human_review", "quarantine"]
    confidence: float = Field(ge=0, le=1)
    executive_summary: str
    rationale: list[str]
    required_controls: list[str]
    evidence_ids: list[str]
    evidence_sha256: list[str] = Field(default_factory=list)
    evidence_set_sha256: str = ""
    receipt_sha256: str = ""
    engine: Literal["gemini_adk", "deterministic_demo"] = "gemini_adk"


class MissionEvent(BaseModel):
    sequence: int
    stage: Literal["intake", "scout", "identity", "guard", "judge", "receipt", "runtime"]
    status: Literal["queued", "running", "completed", "blocked", "failed"]
    title: str
    detail: str
    at: str = Field(default_factory=utc_now)


class MissionRecord(BaseModel):
    mission_id: str
    target_url: str
    objective: str
    demo_case: Literal["safe", "poisoned"] | None = None
    review_after_days: int = 30
    previous_mission_id: str | None = None
    next_review_at: str | None = None
    status: MissionStatus = MissionStatus.QUEUED
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    attempt_count: int = 0
    lease_expires_at: str | None = None
    events: list[MissionEvent] = Field(default_factory=list)
    verdict: MissionVerdict | None = None
    error: str | None = None
    runtime: dict[str, Any] = Field(default_factory=dict)
