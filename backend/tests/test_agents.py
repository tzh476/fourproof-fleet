from app.agents import MODEL_ID, build_root_agent
from app.models import MissionVerdict
from app.orchestrator import enforce_runtime_policy


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
    judge_predecessors = {edge.from_node.name for edge in root.graph.edges if edge.to_node.name == "policy_judge"}
    assert judge_predecessors == {"registry_scout", "identity_verifier", "tool_guard"}
    judge = agents["policy_judge"]
    assert "{scout_report}" not in judge.instruction
    assert [getattr(tool, "name", tool.__name__) for tool in judge.tools] == ["read_specialist_reports"]


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
