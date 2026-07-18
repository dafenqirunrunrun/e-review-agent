import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_leakage_audit_outputs_are_present_and_report_oracle_shortcut():
    summary_path = ROOT / "data/rag/audit/leakage_audit_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["exact_duplicate_count"] == 0
    assert summary["normalized_duplicate_count"] == 0
    assert summary["bge_m3_cosine_checked"] is True
    assert summary["metadata_shortcut_count"] > 0
    assert summary["answer_field_leakage_count"] > 0

    shortcuts = read_jsonl(ROOT / "data/rag/audit/metadata_shortcuts.jsonl")
    shortcut_types = {row["shortcut_type"] for row in shortcuts}
    assert "metadata_match_score_uses_risk_type" in shortcut_types
    assert "metadata_match_score_uses_risk_level" in shortcut_types
    assert "rule_reranker_uses_evidence_keywords" in shortcut_types
    assert "rule_reranker_uses_hard_negative_case_ids" in shortcut_types


def test_strict_synthetic_queries_separate_input_from_labels():
    rows = read_jsonl(ROOT / "data/synthetic/golden_queries/golden_queries_strict_80.jsonl")
    assert len(rows) == 80
    forbidden_top_level = {"expected_risk_type", "expected_risk_level", "relevant_case_ids", "hard_negative_case_ids", "evidence_keywords"}
    forbidden_text = {"after_sales_risk", "negative_review", "normal_review", "CASE-"}
    for row in rows:
        assert forbidden_top_level.isdisjoint(row.keys())
        assert set(row["input"].keys()) == {"query_text", "product_category", "rating", "image_signal"}
        assert len(row["evaluation_labels"]["hard_negative_case_ids"]) >= 3
        query_text = row["input"]["query_text"]
        assert all(value not in query_text for value in forbidden_text)


def test_validity_external_eval_contains_strict_no_oracle_metrics():
    result_path = ROOT / "data/rag/audit/validity_external_eval_results.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["marker"] == "REALWORLD_EXTERNAL_EVAL_BLOCKED"
    assert result["counts"]["strict_synthetic"] == 80
    strict = result["strict_no_oracle"]["hybrid_rerank"]
    assert strict["query_count"] == 80
    assert "hit_at_3" in strict
    assert "hit_at_5" in strict
    assert strict["hit_at_5"] < result["original_oracle"]["hybrid_rerank"]["hit_at_5"]
