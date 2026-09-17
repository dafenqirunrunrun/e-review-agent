from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path

from scripts import run_step213a_lite as benchmark


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213a_lite"
PROMPT = OUTPUT / "local_qwen_router_prompt_v1.md"


@dataclass
class FakeResult:
    content: str
    latency_ms: int = 10
    token_usage_input: int = 20
    token_usage_output: int = 10


class FakeProvider:
    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls = 0

    def complete_json(self, prompt: str) -> FakeResult:
        self.calls += 1
        return FakeResult(self.outputs[min(self.calls - 1, len(self.outputs) - 1)])


def valid_output(**overrides) -> str:
    value = {
        "decision": "CLASSIFY",
        "riskTypes": ["normal_review"],
        "severity": "LOW",
        "confidenceBand": "HIGH",
        "needsHumanReview": False,
        "reasonCodes": ["NORMAL_FEEDBACK"],
    }
    value.update(overrides)
    return json.dumps(value)


def inference(output: dict, **overrides) -> dict:
    value = {
        "schemaValid": True,
        "schemaRetryCount": 0,
        "cacheHit": False,
        "latencyMs": 10,
        "inputTokens": 20,
        "outputTokens": 10,
        "rawOutputHashes": ["abc"],
        "output": output,
        "errorCode": None,
    }
    value.update(overrides)
    return value


def case(**overrides) -> dict:
    value = {
        "caseId": "case-1",
        "riskTypes": ["normal_review"],
        "sourceDataset": "fixture",
        "expressionType": "explicit",
        "difficulty": "easy",
        "multiRisk": False,
        "boundaryType": None,
        "_partition": "VALIDATION",
    }
    value.update(overrides)
    return value


def test_local_model_discovery(tmp_path):
    model = tmp_path / "Qwen3-1.7B"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "model.safetensors").write_bytes(b"x")
    assert benchmark.discover_local_model(model) == model.resolve()


def test_no_external_provider_call_is_wired():
    source = inspect.getsource(benchmark.configure_local_provider)
    assert benchmark.MODEL_PROVIDER_TYPE == "local_qwen3_transformers"
    assert "local://transformers" in source
    assert "api_key_env=\"\"" in source
    assert "requests" not in source and "httpx" not in source


def test_frozen_not_executed_and_sha_unchanged():
    assert benchmark.sha256_file(benchmark.DEFAULT_FROZEN) == benchmark.FROZEN_GOLD_SHA
    if (OUTPUT / "step213a_lite_gate_v1.json").is_file():
        gate = json.loads((OUTPUT / "step213a_lite_gate_v1.json").read_text(encoding="utf-8"))
        assert gate["frozenBenchmarkExecuted"] is False


def test_dataset_read_only_hashes():
    assert benchmark.sha256_file(benchmark.DEFAULT_CALIBRATION) == benchmark.CALIBRATION_SHA
    assert benchmark.sha256_file(benchmark.DEFAULT_BOUNDARY) == benchmark.BOUNDARY_SHA


def test_prompt_hash_and_version_are_stable():
    prompt_hash = hashlib.sha256(PROMPT.read_bytes()).hexdigest().upper()
    assert len(prompt_hash) == 64
    assert "{{REVIEW_TEXT}}" in PROMPT.read_text(encoding="utf-8")
    assert benchmark.BENCHMARK_VERSION.endswith("v1")


def test_schema_validation_accepts_contract_and_rejects_prohibited_risk():
    parsed, error = benchmark.parse_router_output(valid_output())
    assert parsed is not None and error is None
    parsed, error = benchmark.parse_router_output(valid_output(riskTypes=["other"]))
    assert parsed is None and error is not None


def test_format_retry_limit_is_exactly_one(tmp_path):
    provider = FakeProvider(["not-json", "still-not-json", valid_output()])
    result = benchmark.invoke_local_qwen(
        provider=provider,
        prompt="fixture",
        case_id="retry",
        dataset_hash="dataset",
        model_identity="model",
        prompt_hash="prompt",
        cache_dir=tmp_path,
        use_cache=False,
    )
    assert benchmark.MAX_SCHEMA_RETRIES == 1
    assert provider.calls == 2
    assert result["schemaRetryCount"] == 1
    assert result["schemaValid"] is False


def test_multi_risk_scoring_requires_exact_set():
    row = benchmark.evaluate_output(
        case(riskTypes=["paid_review", "rating_manipulation"], multiRisk=True),
        inference({
            "decision": "CLASSIFY", "riskTypes": ["rating_manipulation"], "severity": "HIGH",
            "confidenceBand": "MEDIUM", "needsHumanReview": True, "reasonCodes": ["RATING_SIGNAL"],
        }),
        {"safetyGateTriggered": True},
    )
    assert row["exactMatch"] is False
    assert row["riskTypePrecision"] == 1.0
    assert row["riskTypeRecall"] == 0.5


def test_abstention_scoring_accepts_abstain_or_non_high_human_review():
    abstention_case = case(riskTypes=[], evaluationTarget="ABSTENTION", _partition="BOUNDARY_CHALLENGE")
    direct = benchmark.evaluate_output(
        abstention_case,
        inference({"decision": "ABSTAIN", "riskTypes": [], "severity": "MEDIUM", "confidenceBand": "LOW", "needsHumanReview": True, "reasonCodes": ["AMBIGUOUS"]}),
        {},
    )
    human = benchmark.evaluate_output(
        abstention_case,
        inference({"decision": "CLASSIFY", "riskTypes": ["after_sales_risk"], "severity": "MEDIUM", "confidenceBand": "MEDIUM", "needsHumanReview": True, "reasonCodes": ["AMBIGUOUS"]}),
        {},
    )
    assert direct["abstentionCorrect"] is True
    assert human["abstentionCorrect"] is True


def test_material_safety_error_and_auto_pass_candidate():
    row = benchmark.evaluate_output(
        case(riskTypes=["paid_review"]),
        inference({"decision": "CLASSIFY", "riskTypes": ["normal_review"], "severity": "LOW", "confidenceBand": "HIGH", "needsHumanReview": False, "reasonCodes": ["NORMAL"]}),
        {},
    )
    assert row["materialSafetyError"] is True
    assert row["highRiskAutoPassCandidate"] is True


def test_rule_baseline_immutable_count_and_metrics():
    before = benchmark.sha256_file(benchmark.DEFAULT_RULE_RESULTS)
    rows = [row for row in benchmark.load_jsonl(benchmark.DEFAULT_RULE_RESULTS) if row["partition"] in {"VALIDATION", "BOUNDARY_CHALLENGE"}]
    result = benchmark.rule_baseline(rows)
    assert len(rows) == result["caseCount"] == 100
    assert benchmark.sha256_file(benchmark.DEFAULT_RULE_RESULTS) == before


def test_cache_resume_avoids_duplicate_generation(tmp_path):
    provider = FakeProvider([valid_output()])
    arguments = dict(
        provider=provider,
        prompt="fixture",
        case_id="cached",
        dataset_hash="dataset",
        model_identity="model",
        prompt_hash="prompt",
        cache_dir=tmp_path,
    )
    first = benchmark.invoke_local_qwen(**arguments)
    second = benchmark.invoke_local_qwen(**arguments)
    assert provider.calls == 1
    assert first["cacheHit"] is False
    assert second["cacheHit"] is True


def test_latency_metrics_are_exact_for_small_fixture():
    result = benchmark.latency_metrics([{"latencyMs": value} for value in [10, 20, 30, 40, 50]])
    assert result == {"count": 5, "p50Ms": 30, "p95Ms": 48.0, "p99Ms": 49.6}


def test_quality_metrics_keep_total_and_classification_counts_separate():
    classified = benchmark.evaluate_output(case(), inference(json.loads(valid_output())), {})
    abstention_case = case(riskTypes=[], evaluationTarget="ABSTENTION", _partition="BOUNDARY_CHALLENGE")
    abstention = benchmark.evaluate_output(
        abstention_case,
        inference({"decision": "ABSTAIN", "riskTypes": [], "severity": "MEDIUM", "confidenceBand": "LOW", "needsHumanReview": True, "reasonCodes": ["AMBIGUOUS"]}),
        {},
    )
    metrics = benchmark.quality_metrics([classified, abstention], completed=False)
    assert metrics["caseCount"] == 2
    assert metrics["classificationCaseCount"] == 1


def test_reliability_high_tier_requires_non_safety_low_or_medium_severity():
    base = {"schemaValid": True, "safetyGateTriggered": False, "output": {"decision": "CLASSIFY", "confidenceBand": "HIGH", "needsHumanReview": False, "severity": "LOW"}}
    assert benchmark.reliability_tier(base) == "HIGH_RELIABILITY"
    assert benchmark.reliability_tier({**base, "safetyGateTriggered": True}) == "MEDIUM_RELIABILITY"


def test_security_scan_on_generated_artifacts():
    if not (OUTPUT / "step213a_lite_gate_v1.json").is_file():
        return
    paths = [path for path in OUTPUT.iterdir() if path.is_file()]
    report = ROOT.parent / "docs" / "LOCAL_QWEN_ROUTER_BENCHMARK_REPORT.md"
    if report.is_file():
        paths.append(report)
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert not re.search(r"reviewer(identity|id|name)", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
