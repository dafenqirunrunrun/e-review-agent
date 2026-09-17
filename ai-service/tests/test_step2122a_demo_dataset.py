from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from app.contracts.review_semantics import RISK_TYPE_REGISTRY


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "evaluation_demo"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
REQUIRED = {
    "caseId", "textZh", "sourceDataset", "sourceRowId", "sourceLanguage",
    "translationStatus", "adaptationStatus", "riskTypes", "severity",
    "expressionType", "difficulty", "multiRisk", "ambiguity", "boundaryType",
    "labelSource", "sourceTier", "contentHash",
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text.lower())


def test_demo_dataset_counts_schema_and_candidate_status():
    calibration = load_jsonl(DATA / "router_calibration_candidate_demo_v1.jsonl")
    boundary = load_jsonl(DATA / "boundary_challenge_demo_v1.jsonl")

    assert len(calibration) == 120
    assert len(boundary) == 60
    assert all(REQUIRED.issubset(row) for row in calibration + boundary)
    assert all(row["calibrationStatus"] == "CANDIDATE_ONLY" for row in calibration)
    assert all(set(row["riskTypes"]).issubset(RISK_TYPE_REGISTRY) for row in calibration + boundary)
    assert all(row["contentHash"] == hashlib.sha256(row["textZh"].encode()).hexdigest() for row in calibration + boundary)


def test_boundary_distribution_is_fixed():
    boundary = load_jsonl(DATA / "boundary_challenge_demo_v1.jsonl")
    assert Counter(row["boundaryType"] for row in boundary) == {
        "implicit_or_paraphrase": 15,
        "lexical_mismatch": 10,
        "hard_negative": 15,
        "multi_risk_or_conflict": 10,
        "ambiguous_context": 5,
        "noisy_or_adversarial": 5,
    }


def test_frozen_is_untouched_and_isolated():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() == FROZEN_SHA
    frozen = {normalize(row["reviewText"]) for row in load_jsonl(FROZEN)}
    demo = load_jsonl(DATA / "router_calibration_candidate_demo_v1.jsonl") + load_jsonl(DATA / "boundary_challenge_demo_v1.jsonl")
    assert not frozen.intersection(normalize(row["textZh"]) for row in demo)
    manifest = json.loads((DATA / "dataset_manifest_demo_v1.json").read_text(encoding="utf-8"))
    assert manifest["quality"]["frozenExactOverlap"] == 0
    assert manifest["quality"]["frozenNearOverlap"] == 0
    assert manifest["quality"]["frozenTemplateOverlap"] == 0


def test_only_approved_sources_contribute_text_and_unclear_source_is_skipped():
    registry = json.loads((DATA / "source_registry_demo_v1.json").read_text(encoding="utf-8"))["sources"]
    by_id = {row["sourceId"]: row for row in registry}
    selected = {row["sourceDataset"] for row in load_jsonl(DATA / "router_calibration_candidate_demo_v1.jsonl") + load_jsonl(DATA / "boundary_challenge_demo_v1.jsonl")}
    assert all(by_id[source]["status"] == "APPROVED" for source in selected)
    assert by_id["amazon_reviews_2023"]["status"] == "SKIPPED_LICENSE_UNCLEAR"
    assert by_id["amazon_reviews_2023"]["selectedCount"] == 0


def test_manifest_gates_security_and_ai_usage():
    manifest = json.loads((DATA / "dataset_manifest_demo_v1.json").read_text(encoding="utf-8"))
    assert manifest["gate"] == "PASS_WITH_COVERAGE_LIMITATION"
    assert manifest["quality"]["deterministicCompletenessScore"] == 70
    assert set(manifest["quality"]["gates"].values()) == {"PASS"}
    assert manifest["quality"]["securityViolations"] == []
    usage = json.loads((DATA / "ai_usage_report_demo.json").read_text(encoding="utf-8"))
    assert usage["translationCalls"] == 25
    assert usage["translationCalls"] < 100
    assert "judge" in usage["notes"].lower()


def test_sampling_manifest_is_complete_and_has_no_identity_fields():
    sampling = load_jsonl(DATA / "sampling_manifest_demo_v1.jsonl")
    assert len(sampling) == 180
    assert len({row["caseId"] for row in sampling}) == 180
    payload = json.dumps(sampling, ensure_ascii=False).lower()
    assert "reviewer" not in payload
    assert "user_id" not in payload
    assert "authorization" not in payload
    assert not re.search(r"[a-z]:\\", payload)
