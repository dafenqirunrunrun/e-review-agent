import json

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.agentic_workflow.runtime_checkpoint import FileWorkflowCheckpointStore
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.seeds import seed_policy_documents
from app.risk_calibration.assessment import SmallModelRiskAssessor
from app.risk_calibration.calibrator import fit_isotonic, load_calibrator, save_calibrator
from app.risk_calibration.severity import RiskSeverityEvaluator
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer
from scripts.run_step212_calibration import assert_no_frozen_overlap, build_calibration_cases, load_jsonl


def test_severity_mapping_is_deterministic():
    evaluator = RiskSeverityEvaluator()
    first = evaluator.evaluate(["normal_review"])
    second = evaluator.evaluate(["normal_review"])
    assert first == second
    assert first.severity == "low"
    assert evaluator.evaluate(["rating_manipulation"]).severity == "high"


def test_severity_context_modifier_escalates_organized_high_risk():
    result = RiskSeverityEvaluator().evaluate(["rating_manipulation"], review_text="组织一批账号集中打五星")
    assert result.severity == "critical"
    assert "ORGANIZED_HIGH_IMPACT" in result.severityReasons


def test_small_model_assessment_schema_and_confidence_range():
    result = SmallModelRiskAssessor("missing.json").assess(
        risk_types=["fake_review"], raw_confidence=1.7, reason_codes=[], review_text="虚构评价"
    )
    assert result.schemaVersion == "small-model-risk-assessment-v1"
    assert result.rawConfidence == 1.0
    assert 0.0 <= result.calibratedConfidence <= 1.0
    assert result.complexity in {"low", "medium", "high"}


def test_calibrator_serialization_and_deterministic_output(tmp_path):
    calibrator = fit_isotonic([0.2, 0.4, 0.8, 0.9], [0, 0, 1, 1])
    path = tmp_path / "calibrator.json"
    save_calibrator(calibrator, path, {"frozenGoldExcluded": True})
    loaded = load_calibrator(path)
    assert loaded is not None
    assert loaded.predict(0.65) == loaded.predict(0.65)
    assert 0.0 <= loaded.predict(0.65) <= 1.0
    assert json.loads(path.read_text(encoding="utf-8"))["metadata"]["frozenGoldExcluded"] is True


def test_safety_gate_overrides_local_low_risk_recommendation():
    result = SmallModelRiskAssessor("missing.json").assess(
        risk_types=["normal_review"], raw_confidence=0.95,
        reason_codes=["HIGH_RISK_SAFETY_GATE"], review_text="普通评价",
    )
    assert result.safetyGateOverride is True
    assert result.routingRecommendation == "strict_governance"


def test_calibration_dataset_is_separate_from_frozen_gold():
    cases = build_calibration_cases()
    frozen = load_jsonl(__import__("pathlib").Path("data/benchmarks/review_governance_gold_v1.jsonl"))
    assert len(cases) == 240
    assert all(case["labelSource"].startswith("synthetic_weak_label") for case in cases)
    assert_no_frozen_overlap(cases, frozen)


def test_workflow_attaches_features_without_high_risk_auto_pass(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_CHECKPOINT_ENABLED", "false")
    workflow = AgenticReviewWorkflow(analyzer=MockAnalyzer())
    payload = ReviewAnalyzeRequest(
        reviewId="step212-safety", productId="1", productName="item",
        reviewText="客服威胁上门报复并要求删除差评", rating=1,
    )
    response = workflow.analyze(payload)
    assessment = response.extra["riskAssessment"]
    assert assessment["severity"] in {"high", "critical"}
    assert response.route_decision != "auto_pass"
    assert response.route_decision != "auto_close"


def test_historical_completed_checkpoint_gets_sidecar_assessment_without_retrieval(tmp_path):
    class CountingRetriever(PolicyEvidenceRetriever):
        def __init__(self):
            seed = PolicyEvidenceRetriever.from_documents(seed_policy_documents())
            super().__init__(seed.chunks)
            self.calls = 0

        def search(self, *args, **kwargs):
            self.calls += 1
            return super().search(*args, **kwargs)

    store = FileWorkflowCheckpointStore(tmp_path)
    retriever = CountingRetriever()
    workflow = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever, checkpoint_store=store)
    payload = ReviewAnalyzeRequest(
        reviewId="step212-history", productId="1", productName="item",
        reviewText="五星截图返现", rating=5,
    )
    workflow.analyze(payload)
    checkpoint = store.load(payload.review_id)
    checkpoint.governanceSnapshot["response"]["extra"].pop("riskAssessment", None)
    store.save(checkpoint)
    calls = retriever.calls

    restored = workflow.analyze(payload)

    assert retriever.calls == calls
    assert restored.extra["riskAssessment"]["severity"] in {"high", "critical"}
