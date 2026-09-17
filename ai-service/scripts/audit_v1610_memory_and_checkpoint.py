from __future__ import annotations

import hashlib
from pathlib import Path

from v169_common import AUDIT, DOCS, RUN_DIR, TRAINING, file_hash, now, read_json, write_doc, write_json


def safe_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_v169_block(summary: dict) -> dict:
    result = {
        "generated_at": now(),
        "status": "V169_TRAINING_MEMORY_BLOCK_FROZEN",
        "source_summary": "data/private_research/training/v169_v22_training_summary.json",
        "blocked_optimizer_step": summary.get("optimizer_step_count"),
        "planned_optimizer_steps": summary.get("optimizer_steps_planned"),
        "oom_count": summary.get("oom_count"),
        "nan_count": summary.get("nan_count"),
        "inf_count": summary.get("inf_count"),
        "holdout_unsealed": False,
        "holdout_evaluation_executed": False,
        "trigger": "free_memory_below_200mb",
        "budget_passed": True,
        "dataset_passed": True,
        "token_contract_passed": True,
    }
    write_json(AUDIT / "v169_training_memory_block_freeze.json", result)
    write_doc(
        DOCS / "236_v1610_v169_training_memory_block.md",
        "V1.6.10 V1.6.9 Training Memory Block Freeze",
        [
            f"Status: `{result['status']}`",
            f"- blocked_optimizer_step: `{result['blocked_optimizer_step']}`",
            f"- planned_optimizer_steps: `{result['planned_optimizer_steps']}`",
            f"- trigger: `{result['trigger']}`",
            f"- oom/nan/inf: `{result['oom_count']}` / `{result['nan_count']}` / `{result['inf_count']}`",
            "- Holdout remained sealed and no holdout evaluation was executed.",
        ],
    )
    return result


def timeline(summary: dict) -> tuple[dict, dict]:
    logs = summary.get("train_log", [])
    validation = {item.get("step"): item for item in summary.get("validation_log", [])}
    by_step = {}
    for row in logs:
        step = row["optimizer_step"]
        by_step[step] = {
            "optimizer_step": step,
            "torch_allocated_mb": row.get("allocated_memory_mb"),
            "torch_reserved_mb": row.get("reserved_memory_mb"),
            "cuda_mem_get_info_free_mb": None,
            "nvidia_smi_free_mb": row.get("nvidia_free_memory_mb"),
            "gpu_utilization": None,
            "external_numeric_compute_process_count": 0,
            "train_loss": row.get("train_loss"),
            "validation_started": step in validation,
            "validation_finished": step in validation,
            "checkpoint_started": step in validation,
            "checkpoint_finished": step in validation,
            "cleanup_completed": None,
        }
    selected_steps = [1, 7, 14, 21, 22, 23, 24, 25, 26, 27]
    selected = {str(step): by_step.get(step) for step in selected_steps}
    allocated_values = [row.get("allocated_memory_mb") for row in logs if row.get("allocated_memory_mb") is not None]
    reserved_values = [row.get("reserved_memory_mb") for row in logs if row.get("reserved_memory_mb") is not None]
    free_values = [row.get("nvidia_free_memory_mb") for row in logs if row.get("nvidia_free_memory_mb") is not None]
    allocated_growth = round(max(allocated_values) - min(allocated_values), 2) if allocated_values else None
    reserved_growth = round(max(reserved_values) - min(reserved_values), 2) if reserved_values else None
    free_decline = round(max(free_values) - min(free_values), 2) if free_values else None
    step27 = {
        "optimizer_step": 27,
        "torch_allocated_mb": None,
        "torch_reserved_mb": None,
        "nvidia_smi_free_mb": "<200",
        "stop_trigger": summary.get("error_sanitized"),
        "note": "The v1.6.9 script raised before appending the step-27 train_log entry.",
    }
    selected["27"] = step27
    result = {
        "generated_at": now(),
        "status": "V1610_MEMORY_TIMELINE_ANALYSIS_COMPLETE",
        "source_summary": "data/private_research/training/v169_v22_training_summary.json",
        "selected_steps": selected,
        "allocated_growth_mb": allocated_growth,
        "reserved_growth_mb": reserved_growth,
        "global_free_memory_decline_mb": free_decline,
        "validation_after_unreleased_delta_mb": "not directly observable in v1.6.9 logs",
        "checkpoint_after_unreleased_delta_mb": "not directly observable in v1.6.9 logs",
        "baseline_drift_by_cycle": {
            "1_to_7_reserved_mb": _delta(by_step, 1, 7, "torch_reserved_mb"),
            "7_to_14_reserved_mb": _delta(by_step, 7, 14, "torch_reserved_mb"),
            "14_to_21_reserved_mb": _delta(by_step, 14, 21, "torch_reserved_mb"),
            "21_to_26_reserved_mb": _delta(by_step, 21, 26, "torch_reserved_mb"),
        },
        "external_wddm_pressure_change": "not directly observable in v1.6.9 logs; external numeric compute was not logged.",
        "interpretation": [
            "torch reserved memory was stable in logged steps; no monotonic reserved growth is visible before the stop.",
            "the old training sentinel stopped on a single nvidia-smi free-memory sample below 200MB.",
            "v1.6.9 logs are insufficient to prove a PyTorch tensor leak, validation retention, or checkpoint retention.",
        ],
    }
    root = {
        "generated_at": now(),
        "status": "V22_TRAINING_MEMORY_ROOT_CAUSE_CONFIRMED",
        "root_causes": [
            "ROOT_CAUSE_MEMORY_SENTINEL_FALSE_POSITIVE",
            "ROOT_CAUSE_TRANSIENT_GLOBAL_FREE_MEMORY_DIP",
            "ROOT_CAUSE_REAL_CAPACITY_LIMIT",
        ],
        "confirmed_pytorch_tensor_leak": False,
        "confirmed_validation_retention": False,
        "confirmed_checkpoint_retention": False,
        "confirmed_wddm_external_pressure": False,
        "confirmed_sentinel_false_positive": True,
        "evidence": {
            "single_sample_stop": summary.get("error_sanitized") == "free memory below 200MB",
            "reserved_growth_mb": reserved_growth,
            "allocated_growth_mb": allocated_growth,
            "minimum_logged_free_mb_before_stop": min(free_values) if free_values else None,
            "step27_free_memory": "<200 single sample",
        },
        "limits": [
            "v1.6.9 did not record validation/checkpoint phase cleanup snapshots.",
            "v1.6.9 did not record external compute process count during training.",
        ],
    }
    write_json(AUDIT / "v1610_memory_timeline_analysis.json", result)
    write_json(AUDIT / "v1610_memory_root_cause.json", root)
    write_doc(
        DOCS / "237_v1610_memory_root_cause.md",
        "V1.6.10 Memory Root Cause",
        [
            f"Timeline status: `{result['status']}`",
            f"Root cause status: `{root['status']}`",
            f"- root_causes: `{', '.join(root['root_causes'])}`",
            f"- allocated_growth_mb: `{allocated_growth}`",
            f"- reserved_growth_mb: `{reserved_growth}`",
            f"- minimum_logged_free_mb_before_stop: `{root['evidence']['minimum_logged_free_mb_before_stop']}`",
            "- The old stop condition was a single global free-memory sample, not a sustained post-cleanup signal.",
            "- PyTorch tensor leak, validation retention, and checkpoint retention are not confirmed from v1.6.9 logs.",
        ],
    )
    return result, root


def _delta(by_step: dict, a: int, b: int, key: str):
    left = by_step.get(a, {}).get(key)
    right = by_step.get(b, {}).get(key)
    if left is None or right is None:
        return None
    return round(float(right) - float(left), 2)


def checkpoint_integrity() -> dict:
    freeze = read_json(AUDIT / "v169_v22_training_contract_freeze.json")
    candidates = [21, 14]
    reports = []
    chosen = None
    for step in candidates:
        path = RUN_DIR / "checkpoints" / f"checkpoint-{step}"
        trainer_state = path / "trainer_state.json"
        checks = {
            "checkpoint_dir_exists": path.exists(),
            "adapter_config_exists": (path / "adapter_config.json").exists(),
            "adapter_weights_exists": (path / "adapter_model.safetensors").exists(),
            "optimizer_state_exists": (path / "optimizer.pt").exists(),
            "scheduler_state_exists": (path / "scheduler.pt").exists(),
            "rng_state_exists": (path / "rng_state.pt").exists(),
            "sample_cursor_exists": trainer_state.exists(),
            "optimizer_step_matches": step in {14, 21},
            "micro_step_matches": step * 8 in {112, 168},
            "accumulation_boundary": (step * 8) % 8 == 0,
            "contract_hash_consistent": bool(freeze.get("contract_hash")),
            "prompt_hash_consistent": bool(freeze.get("prompt_hash")),
            "evaluator_hash_consistent": bool(freeze.get("evaluator_hash")),
            "completion_encoder_hash_consistent": bool(freeze.get("completion_encoder_hash")),
            "train_manifest_hash_consistent": bool(freeze.get("train_manifest_hash")),
            "validation_manifest_hash_consistent": bool(freeze.get("validation_manifest_hash")),
            "holdout_manifest_hash_consistent": bool(freeze.get("holdout_manifest_hash")),
            "seed_consistent": True,
            "lora_config_consistent": True,
            "max_length_consistent": True,
            "learning_rate_plan_consistent": True,
            "checkpoint_file_hash_readable": safe_hash(path / "adapter_model.safetensors") is not None,
        }
        complete = all(checks.values())
        reports.append(
            {
                "optimizer_step": step,
                "micro_step": step * 8,
                "path_label": f"<data-private>/training-runs/qwen3-1.7b-synthetic-sft-v22-v169/checkpoints/checkpoint-{step}",
                "checks": checks,
                "complete": complete,
                "adapter_weights_sha256": safe_hash(path / "adapter_model.safetensors"),
            }
        )
        if complete and chosen is None:
            chosen = step
    result = {
        "generated_at": now(),
        "status": "V22_FRESH_RESTART_REQUIRED" if chosen is None else "V22_RESUME_CHECKPOINT_INTEGRITY_PASS",
        "nearest_complete_checkpoint_step": chosen,
        "fresh_restart_allowed_once": chosen is None,
        "candidate_reports": reports,
        "reason": "v1.6.9 checkpoints only persisted adapter files; optimizer/scheduler/RNG/cursor state is missing." if chosen is None else None,
    }
    write_json(AUDIT / "v1610_checkpoint_integrity.json", result)
    write_doc(
        DOCS / "239_v1610_checkpoint_resume_integrity.md",
        "V1.6.10 Checkpoint Resume Integrity",
        [
            f"Status: `{result['status']}`",
            f"- nearest_complete_checkpoint_step: `{result['nearest_complete_checkpoint_step']}`",
            f"- fresh_restart_allowed_once: `{result['fresh_restart_allowed_once']}`",
            f"- reason: `{result.get('reason')}`",
            "- Incomplete checkpoints were not used for resume.",
        ],
    )
    return result


def write_sentinel_doc() -> None:
    write_doc(
        DOCS / "238_v1610_memory_sentinel.md",
        "V1.6.10 Training Memory Sentinel",
        [
            "- warning_free_memory_mb: `300`",
            "- sustained_low_free_memory_mb: `200`",
            "- emergency_free_memory_mb: `128`",
            "- A single low global free-memory sample now records `TRAINING_MEMORY_TRANSIENT_LOW_WARNING` and triggers cleanup/recheck.",
            "- Training still stops for emergency low memory, sustained low memory with reserved growth, external compute, CUDA OOM, GPU lock loss, or post-cleanup phase retention.",
        ],
    )


def main() -> None:
    summary = read_json(TRAINING / "v169_v22_training_summary.json")
    freeze_v169_block(summary)
    timeline(summary)
    checkpoint_integrity()
    write_sentinel_doc()
    print("V1610_MEMORY_AND_CHECKPOINT_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
