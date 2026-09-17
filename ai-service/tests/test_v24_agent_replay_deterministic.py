from __future__ import annotations

from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_same_fixture_same_canonical_outcome_hash() -> None:
    case = synthetic_cases(1)[0]
    hashes = [run_synthetic_agent(case, "memory")["canonicalOutcomeHash"] for _ in range(3)]
    assert len(set(hashes)) == 1


def test_node_order_change_changes_outcome_hash() -> None:
    case = synthetic_cases(1)[0]
    first = run_synthetic_agent(case, "memory")
    changed = dict(first["businessOutcome"])
    changed["orderedNodeTypeSequence"] = list(reversed(changed["orderedNodeTypeSequence"]))
    recorder = __import__("app.agent_trace.recorder", fromlist=["AgentTraceRecorder"]).AgentTraceRecorder()
    assert first["canonicalOutcomeHash"] != recorder.canonical_outcome_hash(changed)
