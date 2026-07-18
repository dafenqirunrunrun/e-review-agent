import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))
AUDIT = ROOT / "data/private_research/audit"
TRAINING = ROOT / "data/private_research/training"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def status(free_mb: int, foreign: int = 0):
    return SimpleNamespace(
        memory_free_mb=free_mb,
        foreign_process_count=foreign,
        utilization_percent=0,
    )


def test_v1610_freezes_v169_memory_block_without_unsealing_holdout():
    freeze = read_json(AUDIT / "v169_training_memory_block_freeze.json")
    assert freeze["status"] == "V169_TRAINING_MEMORY_BLOCK_FROZEN"
    assert freeze["blocked_optimizer_step"] == 27
    assert freeze["planned_optimizer_steps"] == 42
    assert freeze["oom_count"] == 0
    assert freeze["nan_count"] == 0
    assert freeze["inf_count"] == 0
    assert freeze["holdout_unsealed"] is False
    assert freeze["trigger"] == "free_memory_below_200mb"


def test_v1610_root_cause_marks_single_sample_sentinel_not_tensor_leak():
    root = read_json(AUDIT / "v1610_memory_root_cause.json")
    timeline = read_json(AUDIT / "v1610_memory_timeline_analysis.json")
    assert root["status"] == "V22_TRAINING_MEMORY_ROOT_CAUSE_CONFIRMED"
    assert "ROOT_CAUSE_MEMORY_SENTINEL_FALSE_POSITIVE" in root["root_causes"]
    assert root["confirmed_pytorch_tensor_leak"] is False
    assert root["confirmed_validation_retention"] is False
    assert root["confirmed_checkpoint_retention"] is False
    assert root["confirmed_sentinel_false_positive"] is True
    assert timeline["reserved_growth_mb"] == 0.0


def test_v1610_checkpoint_integrity_blocks_incomplete_v169_checkpoint_resume():
    integrity = read_json(AUDIT / "v1610_checkpoint_integrity.json")
    assert integrity["status"] == "V22_FRESH_RESTART_REQUIRED"
    assert integrity["nearest_complete_checkpoint_step"] is None
    assert integrity["fresh_restart_allowed_once"] is True
    step21 = next(item for item in integrity["candidate_reports"] if item["optimizer_step"] == 21)
    assert step21["checks"]["adapter_config_exists"] is True
    assert step21["checks"]["adapter_weights_exists"] is True
    assert step21["checks"]["optimizer_state_exists"] is False
    assert step21["checks"]["scheduler_state_exists"] is False
    assert step21["checks"]["rng_state_exists"] is False
    assert step21["complete"] is False


def test_training_memory_sentinel_does_not_stop_on_single_low_free_sample(monkeypatch):
    from app.training.wddm_memory import training_memory_sentinel

    samples = iter([status(260), status(280), status(310)])
    decision = training_memory_sentinel(
        current_snapshot={"device_global_free_mb": 190, "torch_process_reserved_mb": 6292},
        stable_reserved_baseline_mb=6292,
        status_fn=lambda: next(samples),
        sleep_fn=lambda _: None,
        cleanup_fn=lambda: None,
        lock_reader=lambda: {"pid": os.getpid()},
    )
    assert decision.action == "warning"
    assert decision.reason == "TRAINING_MEMORY_TRANSIENT_LOW_WARNING"
    assert decision.should_stop is False


def test_training_memory_sentinel_stops_on_emergency_sustained_low_memory():
    from app.training.wddm_memory import training_memory_sentinel

    samples = iter([status(120), status(110), status(115)])
    decision = training_memory_sentinel(
        current_snapshot={"device_global_free_mb": 180, "torch_process_reserved_mb": 6292},
        stable_reserved_baseline_mb=6292,
        status_fn=lambda: next(samples),
        sleep_fn=lambda _: None,
        cleanup_fn=lambda: None,
        lock_reader=lambda: {"pid": os.getpid()},
    )
    assert decision.should_stop is True
    assert decision.reason == "TRAINING_MEMORY_EMERGENCY_LOW_FREE_BLOCKED"


def test_training_memory_sentinel_stops_on_external_compute_process():
    from app.training.wddm_memory import training_memory_sentinel

    samples = iter([status(260), status(250, foreign=1), status(240)])
    decision = training_memory_sentinel(
        current_snapshot={"device_global_free_mb": 190, "torch_process_reserved_mb": 6292},
        stable_reserved_baseline_mb=6292,
        status_fn=lambda: next(samples),
        sleep_fn=lambda _: None,
        cleanup_fn=lambda: None,
        lock_reader=lambda: {"pid": os.getpid()},
    )
    assert decision.should_stop is True
    assert decision.reason == "TRAINING_MEMORY_EXTERNAL_COMPUTE_BLOCKED"


def test_v1610_training_summary_if_present_respects_fresh_restart_contract():
    path = TRAINING / "v1610_v22_resumed_training_summary.json"
    if not path.exists():
        return
    summary = read_json(path)
    assert summary["old_adapter_loaded"] is False
    assert summary["holdout_read_during_training"] is False
    assert summary["fresh_restart_occurred"] is True
    assert summary["resume_count"] == 0
    if summary["status"] == "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_PASS":
        assert summary["optimizer_step_count"] == 42
        assert summary["validation_run_count"] == 6
        assert summary["validation_cleanup_status"] == "VALIDATION_GPU_TENSOR_LIFECYCLE_PASS"
        assert summary["checkpoint_cleanup_status"] == "CHECKPOINT_GPU_TENSOR_LIFECYCLE_PASS"
        assert summary["memory_stage_summary"]["raw_stage_log_saved_in_git"] is False


def test_v1610_holdout_evaluated_once_only_after_training_pass():
    training = read_json(TRAINING / "v1610_v22_resumed_training_summary.json")
    holdout = read_json(ROOT / "data/private_research/eval/v1610_v22_holdout_evaluation.json")

    assert training["status"] == "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_PASS"
    assert holdout["status"] == "V22_ENGINEERING_HOLDOUT_EVALUATED_AND_CLOSED"
    assert holdout["holdout_unsealed_once"] is True
    assert holdout["holdout_count"] == 24
    assert holdout["base_metrics"]["real_inference_count"] == 24
    assert holdout["adapter_metrics"]["real_inference_count"] == 24
    assert holdout["raw_outputs_saved_in_git"] is False


def test_v1610_real_text_robustness_and_adapter_gate_are_research_only():
    robustness = read_json(ROOT / "data/private_research/eval/v1610_v22_real_text_robustness.json")
    gate = read_json(AUDIT / "v1610_v22_adapter_value_gate.json")

    assert robustness["status"] == "PRIVATE_REAL_TEXT_V22_ADAPTER_ROBUSTNESS_PASS"
    assert robustness["amazon_sample_count"] == 10
    assert robustness["asap_sample_count"] == 10
    assert robustness["raw_text_saved_in_git"] is False
    assert robustness["raw_outputs_saved_in_git"] is False
    assert gate["status"] == "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_VALUE_GATE"
    assert gate["adapter_value_gate"] in {"GO", "NEUTRAL", "NO_GO"}
    assert gate["adapter_value_gate"] == "NO_GO"
    assert gate["default_candidate"] is False
    assert gate["adapter_final_role"] == "PRIVATE_SYNTHETIC_SFT_V22_ADAPTER_RETAINED_FOR_RESEARCH_ONLY"


def test_v1610_adapter_and_checkpoint_artifacts_are_not_in_git_tree():
    forbidden = {"adapter_config.json", "adapter_model.safetensors", "optimizer.pt", "scheduler.pt", "rng_state.pt"}
    files = {path.name for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts}
    assert forbidden.isdisjoint(files)
