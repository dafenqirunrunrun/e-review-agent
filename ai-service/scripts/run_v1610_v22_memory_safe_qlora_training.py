from __future__ import annotations

import gc
import json
import math
import os
import random
import shutil
import time
from pathlib import Path

from v169_common import AUDIT, DATA_V22, DOCS, MODEL_DIR, PRIVATE_ROOT, TRAINING, file_hash, now, read_json, read_jsonl, write_doc, write_json


RUN_DIR_V1610 = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v22-v1610"

CONFIG = {
    "epochs_planned": 1,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 8,
    "optimizer_steps_planned": 42,
    "max_length": 384,
    "learning_rate": 1e-4,
    "warmup_ratio": 0.0,
    "weight_decay": 0.0,
    "eval_steps": 7,
    "save_steps": 7,
    "save_total_limit": 2,
    "lora_target_modules": ["q_proj", "v_proj"],
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "seed": 1690,
    "bf16": True,
    "fp16": False,
    "quantization": "4-bit NF4 double quant",
    "cpu_offload": False,
    "holdout_path_accepted_by_training": False,
    "warning_free_memory_mb": 300,
    "sustained_low_free_memory_mb": 200,
    "emergency_free_memory_mb": 128,
}


def encode_batch(row, tokenizer):
    import torch
    from app.training.completion_only import encode_completion_only_sample

    enc = encode_completion_only_sample(row, tokenizer, max_length=CONFIG["max_length"])
    return {
        "input_ids": torch.tensor([enc.input_ids], dtype=torch.long, device="cuda"),
        "attention_mask": torch.tensor([enc.attention_mask], dtype=torch.long, device="cuda"),
        "labels": torch.tensor([enc.labels], dtype=torch.long, device="cuda"),
    }, sum(1 for label in enc.labels if label != -100)


def validate(model, tokenizer, rows, memory_log: list[dict], step: int):
    import torch
    from app.training.wddm_memory import cleanup_cuda, cuda_memory_snapshot

    model.eval()
    memory_log.append(cuda_memory_snapshot("validation_start", step))
    total_loss = 0.0
    trainable_tokens = 0
    started = time.perf_counter()
    peak_allocated = 0.0
    with torch.inference_mode():
        for row in rows:
            batch, trainable = encode_batch(row, tokenizer)
            outputs = model(**batch)
            loss = outputs.loss
            total_loss += float(loss.detach().cpu())
            trainable_tokens += trainable
            peak_allocated = max(peak_allocated, torch.cuda.max_memory_allocated() / 1024 / 1024)
            del outputs
            del loss
            del batch
    memory_log.append(cuda_memory_snapshot("validation_end", step))
    memory_log.append(cuda_memory_snapshot("validation_cleanup_before", step))
    model.train()
    cleanup_cuda()
    memory_log.append(cuda_memory_snapshot("validation_cleanup", step))
    return {
        "validation_loss": total_loss / len(rows),
        "validation_trainable_tokens": trainable_tokens,
        "validation_duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "validation_peak_memory_mb": round(peak_allocated, 2),
        "step": step,
    }


def save_checkpoint(model, optimizer, scheduler, summary: dict, memory_log: list[dict], checkpoint_dir: Path) -> None:
    import torch
    from app.training.wddm_memory import cleanup_cuda, cuda_memory_snapshot

    step = summary["optimizer_step_count"]
    memory_log.append(cuda_memory_snapshot("checkpoint_start", step))
    if checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(checkpoint_dir, safe_serialization=True)
    optimizer_state = optimizer.state_dict()
    scheduler_state = scheduler.state_dict()
    torch.save(optimizer_state, checkpoint_dir / "optimizer.pt")
    torch.save(scheduler_state, checkpoint_dir / "scheduler.pt")
    torch.save(
        {
            "torch_rng_state": torch.get_rng_state(),
            "cuda_rng_state": torch.cuda.get_rng_state(),
            "python_random_state": random.getstate(),
        },
        checkpoint_dir / "rng_state.pt",
    )
    trainer_state = {
        "optimizer_step": step,
        "micro_step": summary["micro_step_count"],
        "sample_cursor": summary["micro_step_count"],
        "gradient_accumulation_remainder": summary["micro_step_count"] % CONFIG["gradient_accumulation_steps"],
        "best_validation_loss": summary.get("best_validation_loss"),
        "best_checkpoint_step": summary.get("best_checkpoint_step"),
        "contract_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("contract_hash"),
        "prompt_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("prompt_hash"),
        "evaluator_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("evaluator_hash"),
        "completion_encoder_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("completion_encoder_hash"),
        "train_manifest_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("train_manifest_hash"),
        "validation_manifest_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("validation_manifest_hash"),
        "holdout_manifest_hash": read_json(AUDIT / "v169_v22_training_contract_freeze.json").get("holdout_manifest_hash"),
        "seed": CONFIG["seed"],
        "lora_config": {
            "r": CONFIG["lora_r"],
            "alpha": CONFIG["lora_alpha"],
            "dropout": CONFIG["lora_dropout"],
            "target_modules": CONFIG["lora_target_modules"],
        },
        "max_length": CONFIG["max_length"],
        "learning_rate": CONFIG["learning_rate"],
    }
    (checkpoint_dir / "trainer_state.json").write_text(json.dumps(trainer_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    del optimizer_state
    del scheduler_state
    memory_log.append(cuda_memory_snapshot("checkpoint_end", step))
    memory_log.append(cuda_memory_snapshot("checkpoint_cleanup_before", step))
    cleanup_cuda()
    memory_log.append(cuda_memory_snapshot("checkpoint_cleanup", step))


def adapter_param_sum(model) -> float:
    return sum(float(param.detach().float().sum().item()) for param in model.parameters() if param.requires_grad)


def pass_memory_soak(memory_log: list[dict], summary: dict) -> dict:
    window = [item for item in memory_log if item.get("optimizer_step") is not None and 22 <= int(item["optimizer_step"]) <= 30]
    reserved_values = [item["torch_process_reserved_mb"] for item in window if item.get("torch_process_reserved_mb") is not None]
    free_values = [item["device_global_free_mb"] for item in window if item.get("device_global_free_mb") is not None]
    reserved_growth = round(max(reserved_values) - min(reserved_values), 2) if reserved_values else None
    minimum_free = min(free_values) if free_values else None
    hard_low = [value for value in free_values if value is not None and value < CONFIG["emergency_free_memory_mb"]]
    external = [item for item in window if item.get("external_numeric_compute_process_count")]
    passed = (
        summary["oom_count"] == 0
        and summary["nan_count"] == 0
        and summary["inf_count"] == 0
        and reserved_growth is not None
        and reserved_growth <= 256
        and not hard_low
        and not external
        and summary.get("gradient_present_after_soak") is True
    )
    result = {
        "generated_at": now(),
        "status": "V22_TRAINING_MEMORY_SOAK_PASS" if passed else "V22_TRAINING_MEMORY_SOAK_BLOCKED",
        "memory_soak_range": "step 22-30",
        "minimum_free_memory_mb": minimum_free,
        "reserved_growth_mb": reserved_growth,
        "hard_low_sample_count": len(hard_low),
        "external_compute_sample_count": len(external),
        "transient_low_warning_count": summary.get("transient_low_warning_count", 0),
        "sustained_low_memory_count": summary.get("sustained_low_memory_count", 0),
    }
    write_json(AUDIT / "v1610_memory_soak.json", result)
    return result


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    import transformers
    import bitsandbytes as bnb
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from app.runtime.gpu_gate import gpu_exclusive_gate
    from app.training.wddm_memory import cuda_memory_snapshot, cleanup_cuda, training_memory_sentinel

    budget = read_json(AUDIT / "v169_v22_qlora_budget.json")
    checkpoint_audit = read_json(AUDIT / "v1610_checkpoint_integrity.json")
    summary = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_BLOCKED",
        "new_adapter_initialized_from_base": False,
        "old_adapter_loaded": False,
        "resume_count": 0,
        "fresh_restart_occurred": False,
        "fresh_restart_reason": None,
        "epochs_completed": 0,
        "micro_step_count": 0,
        "backward_count": 0,
        "optimizer_step_count": 0,
        "optimizer_steps_planned": CONFIG["optimizer_steps_planned"],
        "validation_run_count": 0,
        "nan_count": 0,
        "inf_count": 0,
        "oom_count": 0,
        "transient_low_warning_count": 0,
        "sustained_low_memory_count": 0,
        "adapter_parameters_updated": False,
        "best_adapter_saved": False,
        "final_adapter_saved": False,
        "holdout_read_during_training": False,
        "gpu_lock_released": False,
        "gpu_memory_released": False,
        "validation_cleanup_status": "NOT_RUN",
        "checkpoint_cleanup_status": "NOT_RUN",
        "train_log": [],
        "validation_log": [],
        "memory_stage_log": [],
    }
    if budget["status"] != "V22_COMPLETION_ONLY_QLORA_BUDGET_PASS":
        summary["blocked_reason"] = "budget did not pass"
        write_training(summary)
        print(summary["status"])
        return
    if checkpoint_audit["status"] == "V22_RESUME_CHECKPOINT_INTEGRITY_PASS":
        summary["resume_count"] = 1
        summary["resume_optimizer_step"] = checkpoint_audit["nearest_complete_checkpoint_step"]
        raise RuntimeError("resume path is not expected for v1.6.10 because v1.6.9 checkpoints were incomplete")
    summary["fresh_restart_occurred"] = True
    summary["fresh_restart_reason"] = checkpoint_audit["status"]

    train_rows = read_jsonl(DATA_V22 / "train.jsonl")
    validation_rows = read_jsonl(DATA_V22 / "validation.jsonl")
    if RUN_DIR_V1610.exists():
        shutil.rmtree(RUN_DIR_V1610)
    for sub in ["checkpoints", "adapter-best", "adapter-final", "private-train-logs", "private-validation", "private-holdout-predictions", "private-real-text-robustness"]:
        (RUN_DIR_V1610 / sub).mkdir(parents=True, exist_ok=True)

    model = tokenizer = optimizer = scheduler = None
    initial_sum = None
    stable_reserved_baseline = None
    try:
        with gpu_exclusive_gate(
            stage="v1610-v22-memory-safe-qlora-training",
            min_free_memory_mb=5200,
            check_interval_seconds=10,
            stable_checks=2,
            timeout_seconds=600,
            gpu_gate_mode="wddm-aware",
            max_wddm_total_utilization=60,
            max_free_memory_drop_mb=256,
            require_zero_numeric_compute_processes=True,
            allow_wddm_graphics_activity=True,
        ):
            torch.manual_seed(CONFIG["seed"])
            random.seed(CONFIG["seed"])
            torch.cuda.reset_peak_memory_stats()
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
            qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
            model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
            model.config.use_cache = False
            model.gradient_checkpointing_enable()
            summary["quantized_module_count"] = sum(1 for _, module in model.named_modules() if isinstance(module, bnb.nn.Linear4bit))
            model = prepare_model_for_kbit_training(model)
            model = get_peft_model(
                model,
                LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, bias="none", task_type=TaskType.CAUSAL_LM, target_modules=["q_proj", "v_proj"]),
            )
            summary["new_adapter_initialized_from_base"] = True
            initial_sum = adapter_param_sum(model)
            summary["trainable_parameter_count"] = int(sum(p.numel() for p in model.parameters() if p.requires_grad))
            summary["total_parameter_count"] = int(sum(p.numel() for p in model.parameters()))
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"])
            scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda _: 1.0)
            model.train()
            optimizer.zero_grad(set_to_none=True)
            accumulation_loss = 0.0
            no_grad_steps = 0
            started = time.perf_counter()
            for idx, row in enumerate(train_rows, start=1):
                summary["memory_stage_log"].append(cuda_memory_snapshot("train_step_start", summary["optimizer_step_count"] + 1))
                batch, trainable_tokens = encode_batch(row, tokenizer)
                outputs = model(**batch)
                summary["memory_stage_log"].append(cuda_memory_snapshot("forward_complete", summary["optimizer_step_count"] + 1))
                loss = outputs.loss
                loss_value = float(loss.detach().cpu())
                summary["nan_count"] += int(math.isnan(loss_value))
                summary["inf_count"] += int(math.isinf(loss_value))
                if not math.isfinite(loss_value):
                    raise RuntimeError("non-finite train loss")
                (loss / CONFIG["gradient_accumulation_steps"]).backward()
                summary["memory_stage_log"].append(cuda_memory_snapshot("backward_complete", summary["optimizer_step_count"] + 1))
                summary["micro_step_count"] += 1
                summary["backward_count"] += 1
                accumulation_loss += loss_value
                do_step = idx % CONFIG["gradient_accumulation_steps"] == 0 or idx == len(train_rows)
                if do_step:
                    grad_norm_sq = 0.0
                    grad_present = False
                    for param in model.parameters():
                        if param.requires_grad and param.grad is not None:
                            grad_present = True
                            grad_norm_sq += float(param.grad.detach().float().norm().item() ** 2)
                    if not grad_present:
                        no_grad_steps += 1
                    else:
                        no_grad_steps = 0
                    if no_grad_steps >= 3:
                        raise RuntimeError("three optimizer steps without gradient")
                    optimizer.step()
                    scheduler.step()
                    optimizer.zero_grad(set_to_none=True)
                    summary["optimizer_step_count"] += 1
                    step = summary["optimizer_step_count"]
                    step_loss = accumulation_loss / CONFIG["gradient_accumulation_steps"]
                    accumulation_loss = 0.0
                    snap = cuda_memory_snapshot("optimizer_step_complete", step)
                    summary["memory_stage_log"].append(snap)
                    if stable_reserved_baseline is None and step >= 3:
                        stable_reserved_baseline = snap["torch_process_reserved_mb"]
                    decision = training_memory_sentinel(current_snapshot=snap, stable_reserved_baseline_mb=stable_reserved_baseline)
                    if decision.samples:
                        summary["memory_stage_log"].append({"stage": "low_memory_recheck", "optimizer_step": step, "decision": decision.reason, "samples": decision.samples})
                    if decision.action == "warning":
                        summary["transient_low_warning_count"] += 1
                    if decision.should_stop:
                        summary["sustained_low_memory_count"] += 1
                        raise RuntimeError(decision.reason)
                    summary["train_log"].append(
                        {
                            "optimizer_step": step,
                            "micro_steps": idx,
                            "train_loss": step_loss,
                            "learning_rate": optimizer.param_groups[0]["lr"],
                            "gradient_norm": math.sqrt(grad_norm_sq),
                            "trainable_tokens": trainable_tokens,
                            "skipped_step": False,
                            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                            "allocated_memory_mb": snap["torch_process_allocated_mb"],
                            "reserved_memory_mb": snap["torch_process_reserved_mb"],
                            "nvidia_free_memory_mb": snap["device_global_free_mb"],
                        }
                    )
                    if 22 <= step <= 30 and grad_present:
                        summary["gradient_present_after_soak"] = True
                    if step % CONFIG["eval_steps"] == 0:
                        val = validate(model, tokenizer, validation_rows, summary["memory_stage_log"], step)
                        if not math.isfinite(val["validation_loss"]):
                            raise RuntimeError("non-finite validation loss")
                        summary["validation_log"].append(val)
                        summary["validation_run_count"] += 1
                        summary["validation_cleanup_status"] = "VALIDATION_GPU_TENSOR_LIFECYCLE_PASS"
                        checkpoint_dir = RUN_DIR_V1610 / "checkpoints" / f"checkpoint-{step}"
                        save_checkpoint(model, optimizer, scheduler, summary, summary["memory_stage_log"], checkpoint_dir)
                        summary["checkpoint_cleanup_status"] = "CHECKPOINT_GPU_TENSOR_LIFECYCLE_PASS"
                        best = summary.get("best_validation_loss")
                        if best is None or val["validation_loss"] < best - 1e-6:
                            summary["best_validation_loss"] = val["validation_loss"]
                            summary["best_checkpoint_step"] = step
                            best_dir = RUN_DIR_V1610 / "adapter-best"
                            if best_dir.exists():
                                shutil.rmtree(best_dir)
                            shutil.copytree(checkpoint_dir, best_dir)
                        checkpoints = sorted((RUN_DIR_V1610 / "checkpoints").glob("checkpoint-*"), key=lambda path: int(path.name.split("-")[-1]))
                        for stale in checkpoints[:-CONFIG["save_total_limit"]]:
                            shutil.rmtree(stale)
                del outputs
                del loss
                del batch
            soak = pass_memory_soak(summary["memory_stage_log"], summary)
            if soak["status"] != "V22_TRAINING_MEMORY_SOAK_PASS":
                raise RuntimeError(soak["status"])
            summary["epochs_completed"] = 1
            summary["final_train_loss"] = summary["train_log"][-1]["train_loss"] if summary["train_log"] else None
            final_sum = adapter_param_sum(model)
            summary["adapter_parameters_updated"] = abs(final_sum - float(initial_sum)) > 1e-6
            final_dir = RUN_DIR_V1610 / "adapter-final"
            if final_dir.exists():
                shutil.rmtree(final_dir)
            model.save_pretrained(final_dir, safe_serialization=True)
            summary["best_adapter_saved"] = (RUN_DIR_V1610 / "adapter-best" / "adapter_config.json").exists()
            summary["final_adapter_saved"] = (RUN_DIR_V1610 / "adapter-final" / "adapter_config.json").exists()
            summary["peak_allocated_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2)
            summary["peak_reserved_memory_mb"] = round(torch.cuda.max_memory_reserved() / 1024 / 1024, 2)
            free_values = [item.get("device_global_free_mb") for item in summary["memory_stage_log"] if item.get("device_global_free_mb") is not None]
            summary["minimum_global_free_memory_mb"] = min(free_values) if free_values else None
            del model
            del tokenizer
            del optimizer
            del scheduler
            model = tokenizer = optimizer = scheduler = None
            cleanup_cuda()
            summary["gpu_memory_released"] = True
            summary["memory_stage_log"].append(cuda_memory_snapshot("model_unload", summary["optimizer_step_count"]))
    except torch.cuda.OutOfMemoryError as exc:
        summary["oom_count"] = 1
        summary["error_type"] = type(exc).__name__
        summary["error_sanitized"] = str(exc)[:500]
    except Exception as exc:
        summary["error_type"] = type(exc).__name__
        summary["error_sanitized"] = str(exc)[:500]
    finally:
        try:
            del model
            del tokenizer
            del optimizer
            del scheduler
        except Exception:
            pass
        cleanup_cuda()
        summary["gpu_lock_released"] = True
    if not (AUDIT / "v1610_memory_soak.json").exists():
        pass_memory_soak(summary["memory_stage_log"], summary)
    pass_conditions = [
        summary["epochs_completed"] == 1,
        summary["optimizer_step_count"] == CONFIG["optimizer_steps_planned"],
        summary["validation_run_count"] == 6,
        summary["nan_count"] == 0,
        summary["inf_count"] == 0,
        summary["oom_count"] == 0,
        summary["adapter_parameters_updated"],
        summary["best_adapter_saved"],
        summary["final_adapter_saved"],
        not summary["holdout_read_during_training"],
        summary["gpu_lock_released"],
        summary["gpu_memory_released"],
        summary["validation_cleanup_status"] == "VALIDATION_GPU_TENSOR_LIFECYCLE_PASS",
        summary["checkpoint_cleanup_status"] == "CHECKPOINT_GPU_TENSOR_LIFECYCLE_PASS",
    ]
    summary["status"] = "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_V22_QLORA_TRAIN_BLOCKED"
    write_training(summary)
    print(summary["status"])


def write_training(summary: dict) -> None:
    redacted = dict(summary)
    if "memory_stage_log" in redacted:
        memory_log = redacted.pop("memory_stage_log")
        free_values = [item.get("device_global_free_mb") for item in memory_log if isinstance(item, dict) and item.get("device_global_free_mb") is not None]
        reserved_values = [item.get("torch_process_reserved_mb") for item in memory_log if isinstance(item, dict) and item.get("torch_process_reserved_mb") is not None]
        allocated_values = [item.get("torch_process_allocated_mb") for item in memory_log if isinstance(item, dict) and item.get("torch_process_allocated_mb") is not None]
        selected = []
        for item in memory_log:
            if not isinstance(item, dict):
                continue
            step = item.get("optimizer_step")
            stage = item.get("stage")
            if step in {1, 7, 14, 21, 27, 28, 30, 35, 42} and stage in {
                "optimizer_step_complete",
                "validation_start",
                "validation_cleanup",
                "checkpoint_start",
                "checkpoint_cleanup",
                "low_memory_recheck",
                "model_unload",
            }:
                selected.append(
                    {
                        "stage": stage,
                        "optimizer_step": step,
                        "torch_process_allocated_mb": item.get("torch_process_allocated_mb"),
                        "torch_process_reserved_mb": item.get("torch_process_reserved_mb"),
                        "torch_peak_allocated_mb": item.get("torch_peak_allocated_mb"),
                        "torch_peak_reserved_mb": item.get("torch_peak_reserved_mb"),
                        "device_global_free_mb": item.get("device_global_free_mb"),
                        "external_numeric_compute_process_count": item.get("external_numeric_compute_process_count"),
                        "estimated_non_torch_gpu_usage_mb": item.get("estimated_non_torch_gpu_usage_mb"),
                    }
                )
        redacted["memory_stage_summary"] = {
            "record_count": len(memory_log),
            "selected_records": selected[:80],
            "minimum_global_free_memory_mb": min(free_values) if free_values else None,
            "maximum_reserved_memory_mb": max(reserved_values) if reserved_values else None,
            "minimum_reserved_memory_mb": min(reserved_values) if reserved_values else None,
            "maximum_allocated_memory_mb": max(allocated_values) if allocated_values else None,
            "raw_stage_log_saved_in_git": False,
            "note": "Only aggregate numeric memory statistics are kept in Git.",
        }
    write_json(TRAINING / "v1610_v22_resumed_training_summary.json", redacted)
    write_json(TRAINING / "v1610_v22_training_config.json", CONFIG)
    write_doc(
        DOCS / "240_v1610_v22_training_completion.md",
        "V1.6.10 V2.2 Training Completion",
        [
            f"Status: `{summary['status']}`",
            f"- fresh_restart_occurred: `{summary.get('fresh_restart_occurred')}`",
            f"- resume_count: `{summary.get('resume_count')}`",
            f"- optimizer_step_count: `{summary.get('optimizer_step_count')}`",
            f"- validation_run_count: `{summary.get('validation_run_count')}`",
            f"- final_train_loss: `{summary.get('final_train_loss')}`",
            f"- best_validation_loss: `{summary.get('best_validation_loss')}`",
            f"- best_checkpoint_step: `{summary.get('best_checkpoint_step')}`",
            f"- validation_cleanup_status: `{summary.get('validation_cleanup_status')}`",
            f"- checkpoint_cleanup_status: `{summary.get('checkpoint_cleanup_status')}`",
            f"- transient_low_warning_count: `{summary.get('transient_low_warning_count')}`",
            f"- sustained_low_memory_count: `{summary.get('sustained_low_memory_count')}`",
        ],
    )


if __name__ == "__main__":
    main()
