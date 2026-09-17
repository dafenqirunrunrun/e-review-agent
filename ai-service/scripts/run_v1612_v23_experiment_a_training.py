from __future__ import annotations

import gc
import json
import math
import random
import shutil
import time
from pathlib import Path

from v169_common import AUDIT, DOCS, MODEL_DIR, PRIVATE_ROOT, TRAINING, now, read_json, read_jsonl, write_doc, write_json

DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"
RUN_DIR = PRIVATE_ROOT / ("training" + "-runs") / "qwen3-1.7b-synthetic-sft-v23-v1612"

CONFIG = {
    "epochs_planned": 1,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 8,
    "optimizer_steps_planned": 72,
    "max_length": 384,
    "learning_rate": 1e-4,
    "eval_steps": 12,
    "save_steps": 12,
    "lora_target_modules": ["q_proj", "v_proj"],
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "seed": 1612,
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
    total = 0.0
    trainable_tokens = 0
    started = time.perf_counter()
    with torch.inference_mode():
        for row in rows:
            batch, trainable = encode_batch(row, tokenizer)
            outputs = model(**batch)
            total += float(outputs.loss.detach().cpu())
            trainable_tokens += trainable
            del outputs, batch
    model.train()
    cleanup_cuda()
    memory_log.append(cuda_memory_snapshot("validation_cleanup", step))
    return {"step": step, "validation_loss": total / len(rows), "validation_trainable_tokens": trainable_tokens, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}


def save_checkpoint(model, optimizer, scheduler, summary: dict, checkpoint_dir: Path) -> None:
    import torch

    if checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(checkpoint_dir, safe_serialization=True)
    torch.save(optimizer.state_dict(), checkpoint_dir / "optimizer.pt")
    torch.save(scheduler.state_dict(), checkpoint_dir / "scheduler.pt")
    torch.save({"torch_rng_state": torch.get_rng_state(), "cuda_rng_state": torch.cuda.get_rng_state(), "python_random_state": random.getstate()}, checkpoint_dir / "rng_state.pt")
    (checkpoint_dir / "trainer_state.json").write_text(json.dumps({"optimizer_step": summary["optimizer_step_count"], "micro_step": summary["micro_step_count"], "best_validation_loss": summary.get("best_validation_loss"), "best_checkpoint_step": summary.get("best_checkpoint_step"), "config": CONFIG}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def adapter_param_sum(model) -> float:
    return sum(float(param.detach().float().sum().item()) for param in model.parameters() if param.requires_grad)


def write_training(summary: dict) -> None:
    write_json(AUDIT / "v1612_experiment_a_training_summary.json", summary)
    write_json(TRAINING / "v1612_experiment_a_training_log.json", {"status": summary["status"], "train_log": summary["train_log"], "validation_log": summary["validation_log"], "memory_stage_log": summary["memory_stage_log"]})
    write_doc(DOCS / "255_v1612_experiment_a_training.md", "V1.6.12 Experiment A Training", [f"Status: `{summary['status']}`", f"- optimizer_step_count: `{summary.get('optimizer_step_count')}`", f"- validation_run_count: `{summary.get('validation_run_count')}`", f"- best_validation_loss: `{summary.get('best_validation_loss')}`", f"- oom/nan/inf: `{summary.get('oom_count')}` / `{summary.get('nan_count')}` / `{summary.get('inf_count')}`"])


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    import transformers
    import bitsandbytes as bnb
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from app.runtime.gpu_gate import gpu_exclusive_gate
    from app.training.wddm_memory import cleanup_cuda, cuda_memory_snapshot, training_memory_sentinel

    budget = read_json(AUDIT / "v1612_v23_qlora_budget.json")
    summary = {
        "generated_at": now(),
        "status": "PRIVATE_SYNTHETIC_SFT_V23_EXPERIMENT_A_TRAIN_BLOCKED",
        "new_adapter_initialized_from_base": False,
        "old_adapter_loaded": False,
        "resume_count": 0,
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
        "train_log": [],
        "validation_log": [],
        "memory_stage_log": [],
    }
    if budget["status"] != "V23_EXPERIMENT_A_QLORA_BUDGET_PASS":
        summary["blocked_reason"] = "budget did not pass"
        write_training(summary)
        print(summary["status"])
        return
    train_rows = read_jsonl(DATA_V23 / "train.jsonl")
    validation_rows = read_jsonl(DATA_V23 / "validation.jsonl")
    random.Random(CONFIG["seed"]).shuffle(train_rows)
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)
    for sub in ["checkpoints", "adapter-best", "adapter-final", "private-train-logs", "private-validation", "private-holdout-predictions"]:
        (RUN_DIR / sub).mkdir(parents=True, exist_ok=True)
    model = tokenizer = optimizer = scheduler = None
    initial_sum = None
    stable_reserved_baseline = None
    try:
        with gpu_exclusive_gate(stage="v1612-v23-experiment-a-training", min_free_memory_mb=5200, check_interval_seconds=10, stable_checks=2, timeout_seconds=600, gpu_gate_mode="wddm-aware", max_wddm_total_utilization=60, max_free_memory_drop_mb=256, require_zero_numeric_compute_processes=True, allow_wddm_graphics_activity=True):
            torch.manual_seed(CONFIG["seed"])
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
            qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
            model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
            model.config.use_cache = False
            model.gradient_checkpointing_enable()
            quantized_module_count = sum(1 for _, module in model.named_modules() if isinstance(module, bnb.nn.Linear4bit))
            model = prepare_model_for_kbit_training(model)
            model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, bias="none", task_type=TaskType.CAUSAL_LM, target_modules=["q_proj", "v_proj"]))
            summary["new_adapter_initialized_from_base"] = True
            summary["quantized_module_count"] = quantized_module_count
            initial_sum = adapter_param_sum(model)
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=CONFIG["learning_rate"])
            scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
            model.train()
            optimizer.zero_grad(set_to_none=True)
            summary["memory_stage_log"].append(cuda_memory_snapshot("train_start", 0))
            for row in train_rows:
                batch, trainable_tokens = encode_batch(row, tokenizer)
                outputs = model(**batch)
                loss = outputs.loss / CONFIG["gradient_accumulation_steps"]
                loss_value = float(loss.detach().float().item())
                summary["nan_count"] += int(math.isnan(loss_value))
                summary["inf_count"] += int(math.isinf(loss_value))
                loss.backward()
                summary["backward_count"] += 1
                summary["micro_step_count"] += 1
                summary["train_log"].append({"micro_step": summary["micro_step_count"], "loss": loss_value * CONFIG["gradient_accumulation_steps"], "trainable_tokens": trainable_tokens})
                del outputs, loss, batch
                if summary["micro_step_count"] % CONFIG["gradient_accumulation_steps"] == 0:
                    optimizer.step()
                    scheduler.step()
                    optimizer.zero_grad(set_to_none=True)
                    summary["optimizer_step_count"] += 1
                    snapshot = cuda_memory_snapshot("optimizer_step", summary["optimizer_step_count"])
                    summary["memory_stage_log"].append(snapshot)
                    if stable_reserved_baseline is None and snapshot.get("torch_process_reserved_mb"):
                        stable_reserved_baseline = snapshot["torch_process_reserved_mb"]
                    decision = training_memory_sentinel(current_snapshot=snapshot, stable_reserved_baseline_mb=stable_reserved_baseline)
                    if decision.action == "warning":
                        summary["transient_low_warning_count"] += 1
                    if decision.should_stop:
                        summary["sustained_low_memory_count"] += 1
                        summary["blocked_reason"] = decision.reason
                        break
                    step = summary["optimizer_step_count"]
                    if step % CONFIG["eval_steps"] == 0:
                        val = validate(model, tokenizer, validation_rows, summary["memory_stage_log"], step)
                        summary["validation_log"].append(val)
                        summary["validation_run_count"] += 1
                        if summary.get("best_validation_loss") is None or val["validation_loss"] < summary["best_validation_loss"]:
                            summary["best_validation_loss"] = val["validation_loss"]
                            summary["best_checkpoint_step"] = step
                            model.save_pretrained(RUN_DIR / "adapter-best", safe_serialization=True)
                            summary["best_adapter_saved"] = True
                        save_checkpoint(model, optimizer, scheduler, summary, RUN_DIR / "checkpoints" / f"checkpoint-step-{step:03d}")
                if summary["optimizer_step_count"] >= CONFIG["optimizer_steps_planned"] or summary["sustained_low_memory_count"]:
                    break
            summary["epochs_completed"] = 1 if summary["optimizer_step_count"] == CONFIG["optimizer_steps_planned"] else 0
            final_sum = adapter_param_sum(model)
            summary["adapter_parameters_updated"] = initial_sum is not None and abs(final_sum - initial_sum) > 1e-6
            model.save_pretrained(RUN_DIR / "adapter-final", safe_serialization=True)
            summary["final_adapter_saved"] = True
            cleanup_cuda()
            summary["memory_stage_log"].append(cuda_memory_snapshot("train_cleanup", summary["optimizer_step_count"]))
            passed = summary["optimizer_step_count"] == 72 and summary["validation_run_count"] == 6 and summary["nan_count"] == 0 and summary["inf_count"] == 0 and summary["oom_count"] == 0 and summary["best_adapter_saved"] and summary["final_adapter_saved"] and summary["adapter_parameters_updated"] and not summary["holdout_read_during_training"]
            summary["status"] = "PRIVATE_SYNTHETIC_SFT_V23_EXPERIMENT_A_TRAIN_PASS" if passed else "PRIVATE_SYNTHETIC_SFT_V23_EXPERIMENT_A_TRAIN_BLOCKED"
    except torch.cuda.OutOfMemoryError as exc:
        summary.update({"oom_count": 1, "error_type": type(exc).__name__})
    except Exception as exc:
        summary.update({"error_type": type(exc).__name__, "error_sanitized": str(exc)[:500]})
    finally:
        try:
            del model, tokenizer, optimizer, scheduler
        except Exception:
            pass
        gc.collect()
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, "ipc_collect"):
                    torch.cuda.ipc_collect()
        except Exception:
            pass
        summary["gpu_lock_released"] = True
        summary["gpu_memory_released"] = True
    write_training(summary)
    print(summary["status"])


if __name__ == "__main__":
    main()
