import json
import subprocess
import sys
from pathlib import Path

from app.metrics.human_review import RouteMetricInput, compute_human_review_route_metrics, route_metric_input_from_labels


ROOT = Path(__file__).resolve().parents[2]


def test_compute_human_review_route_metrics_confusion_matrix():
    rows = [
        RouteMetricInput(True, True, True),
        RouteMetricInput(True, False, True),
        RouteMetricInput(False, True, False),
        RouteMetricInput(False, False, False),
    ]

    metrics = compute_human_review_route_metrics(rows)

    assert metrics["sample_count"] == 4
    assert metrics["true_positive"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["human_review_accuracy"] == 0.5
    assert metrics["human_review_precision"] == 0.5
    assert metrics["human_review_recall"] == 0.5
    assert metrics["human_review_f1"] == 0.5
    assert metrics["high_risk_review_recall"] == 0.5
    assert metrics["review_trigger_rate"] == 0.5
    assert metrics["unsafe_auto_pass_rate"] == 0.5


def test_route_metric_input_forces_human_review_on_visual_failures():
    row = {
        "risk_type": "normal_review",
        "risk_level": "low",
        "visual_tool_status": "failed",
        "text_image_consistency": "consistent",
    }

    metric_input = route_metric_input_from_labels(row)

    assert metric_input.expected_should_review is False
    assert metric_input.predicted_should_review is True


def test_route_calibration_script_keeps_realworld_blocked_but_outputs_metrics():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/calibrate_multimodal_human_review_route.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/eval/route_calibration_results.json").read_text(encoding="utf-8"))
    assert result["marker"] == "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED"
    assert result["calibration_status"] == "synthetic_only_not_real_calibration"
    assert result["counts"]["synthetic_validation"] > 0
    metrics = result["synthetic_label_policy_sanity_check"]
    assert metrics["sample_count"] == result["counts"]["synthetic_validation"]
    assert "unsafe_auto_pass_rate" in metrics
    assert "high_risk_review_recall" in metrics
