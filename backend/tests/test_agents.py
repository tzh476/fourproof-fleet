import pytest
from pydantic import ValidationError

from app.agents import (
    FIXED_LLM_CALLS_PER_MISSION,
    MAX_LLM_CALLS_PER_MISSION,
    MAX_OUTPUT_TOKENS_PER_CALL,
    MODEL_ID,
    build_judge_agent,
    build_specialist_agents,
)
from app.models import MissionVerdict, ModelVerdict
from app.orchestrator import enforce_runtime_policy, live_run_config, seal_verdict, single_agent_run_config


def test_adk_fanout_has_three_specialists_and_one_final_judge() -> None:
    assert MODEL_ID == "gemini-3.5-flash"
    specialists = list(build_specialist_agents())
    judge = build_judge_agent()
    agents = [*specialists, judge]
    assert {agent.name for agent in specialists} == {"registry_scout", "identity_verifier", "tool_guard"}
    assert {agent.output_key for agent in specialists} == {"scout_report", "identity_report", "guard_report"}
    assert all(agent.model == MODEL_ID for agent in specialists)
    assert all(not agent.tools for agent in specialists)
    assert all("evidence packet" in agent.instruction for agent in specialists)
    assert all(agent.output_schema is None for agent in specialists)
    assert "specialist_findings_json" in judge.instruction
    assert not judge.tools
    assert judge.output_schema is None
    assert FIXED_LLM_CALLS_PER_MISSION == 4
    assert MAX_LLM_CALLS_PER_MISSION == 8
    assert MAX_OUTPUT_TOKENS_PER_CALL == 2_048
    assert all(agent.generate_content_config.max_output_tokens == 2_048 for agent in agents)
    assert all(agent.generate_content_config.thinking_config.thinking_budget == 0 for agent in agents)
    assert all(agent.generate_content_config.thinking_config.include_thoughts is False for agent in agents)
    assert live_run_config().max_llm_calls == 8
    assert single_agent_run_config().max_llm_calls == 1


def test_model_verdict_normalizes_single_string_list_fields() -> None:
    verdict = ModelVerdict.model_validate(
        {
            "action": "quarantine",
            "confidence": 0.98,
            "executive_summary": "Blocked by the fail-closed onboarding policy.",
            "rationale": "Prompt injection and secret exfiltration were detected.",
            "required_controls": "Human review before any sandbox access.",
            "evidence_ids": "guard-scan",
        }
    )
    assert verdict.rationale == ["Prompt injection and secret exfiltration were detected."]
    assert verdict.required_controls == ["Human review before any sandbox access."]
    assert verdict.evidence_ids == ["guard-scan"]


def test_model_verdict_rejects_unknown_scalar_evidence_id() -> None:
    with pytest.raises(ValidationError, match="evidence_ids"):
        ModelVerdict.model_validate(
            {
                "action": "quarantine",
                "confidence": 0.98,
                "executive_summary": "Blocked by the fail-closed onboarding policy.",
                "rationale": "Prompt injection was detected.",
                "required_controls": [],
                "evidence_ids": "invented-evidence",
            }
        )


def test_runtime_policy_overrides_model_allow_when_guard_has_injection() -> None:
    model_verdict = MissionVerdict(
        action="allow_sandbox",
        confidence=0.6,
        executive_summary="Model suggested sandbox access.",
        rationale=[],
        required_controls=[],
        evidence_ids=["guard-scan"],
    )
    enforced = enforce_runtime_policy(
        model_verdict,
        {"identity_state": "verified", "contradictions": []},
        {"injection_signals": ["instruction_override"], "endpoint_state": "reachable"},
    )
    assert enforced.action == "quarantine"
    assert enforced.confidence == 0.99
    assert "no production activation" in enforced.required_controls


def test_runtime_policy_removes_sandbox_when_identity_is_only_declared() -> None:
    model_verdict = MissionVerdict(
        action="allow_sandbox",
        confidence=0.8,
        executive_summary="Model suggested sandbox access.",
        rationale=[],
        required_controls=[],
        evidence_ids=["identity-claim"],
    )
    enforced = enforce_runtime_policy(
        model_verdict,
        {"identity_state": "declared", "contradictions": []},
        {"injection_signals": [], "endpoint_state": "reachable"},
    )
    assert enforced.action == "human_review"


def test_evidence_set_is_stable_while_run_specific_receipt_can_change() -> None:
    first = MissionVerdict(
        action="human_review",
        confidence=0.91,
        executive_summary="First typed explanation.",
        rationale=["Identity remains declared."],
        required_controls=["human approval"],
        evidence_ids=["identity-claim"],
    )
    second = first.model_copy(update={"executive_summary": "A different valid typed explanation."})
    first_sealed = seal_verdict(first, ["a" * 64])
    second_sealed = seal_verdict(second, ["a" * 64])

    assert first_sealed.evidence_set_sha256 == second_sealed.evidence_set_sha256
    assert first_sealed.receipt_sha256 != second_sealed.receipt_sha256
