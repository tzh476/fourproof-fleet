from app.agents import MAX_LLM_CALLS_PER_MISSION, MAX_OUTPUT_TOKENS_PER_CALL, MODEL_ID, build_root_agent
from app.models import MissionVerdict
from app.orchestrator import enforce_runtime_policy, live_run_config, seal_verdict


def test_adk_workflow_graph_has_parallel_specialists_and_final_judge() -> None:
    root = build_root_agent()
    assert MODEL_ID == "gemini-3.5-flash"
    assert root.name == "fourproof_fleet"
    assert root.max_concurrency == 3
    agents = {node.name: node for node in root.graph.nodes if node.name != "__START__"}
    assert set(agents) == {"registry_scout", "identity_verifier", "tool_guard", "policy_judge"}
    specialists = [agents[name] for name in ["registry_scout", "identity_verifier", "tool_guard"]]
    assert {agent.output_key for agent in specialists} == {"scout_report", "identity_report", "guard_report"}
    assert all(agent.model == MODEL_ID for agent in specialists)
    assert all(not agent.tools for agent in specialists)
    assert all("evidence packet" in agent.instruction for agent in specialists)
    assert all(agent.output_schema is None for agent in specialists)
    judge_predecessors = {edge.from_node.name for edge in root.graph.edges if edge.to_node.name == "policy_judge"}
    assert judge_predecessors == {"registry_scout", "identity_verifier", "tool_guard"}
    judge = agents["policy_judge"]
    assert "{scout_report}" not in judge.instruction
    assert [getattr(tool, "name", tool.__name__) for tool in judge.tools] == ["read_specialist_reports"]
    assert judge.output_schema is None
    assert MAX_LLM_CALLS_PER_MISSION == 8
    assert MAX_OUTPUT_TOKENS_PER_CALL == 2_048
    assert all(agent.generate_content_config.max_output_tokens == 2_048 for agent in agents.values())
    assert all(agent.generate_content_config.thinking_config.thinking_budget == 0 for agent in agents.values())
    assert all(agent.generate_content_config.thinking_config.include_thoughts is False for agent in agents.values())
    assert live_run_config().max_llm_calls == 8


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
