from __future__ import annotations

import gc
import math
import time
from pathlib import Path

from v169_common import AUDIT, DOCS, MODEL_DIR, PRIVATE_ROOT, nvidia_smi, now, read_json, read_jsonl, write_doc, write_json

DATA_V23 = PRIVATE_ROOT / "synthetic-sft-v23"


def main() -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-service"))
    import torch
    import transformers
    import bitsandbytes as bnb
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from app.runtime.gpu_gate import gpu_exclusive_gate
    from app.training.completion_only import encode_completion_only_sample

    freeze = read_json(AUDIT / "v1612_experiment_a_contract_freeze.json")
    result = {"generated_at": now(), "status": "V23_EXPERIMENT_A_QLORA_BUDGET_BLOCKED", "gpu_lock_release_success": False, "oom": 0, "nan": 0, "inf": 0}
    if freeze["status"] != "V23_EXPERIMENT_A_CONTRACT_FROZEN":
        result["blocked_reason"] = "contract freeze did not pass"
        write(result)
        print(result["status"])
        return
    tokenizer = model = optimizer = None
    try:
        with gpu_exclusive_gate(stage="v1612-v23-qlora-budget", min_free_memory_mb=5200, check_interval_seconds=10, stable_checks=2, timeout_seconds=600, gpu_gate_mode="wddm-aware", max_wddm_total_utilization=60, max_free_memory_drop_mb=256, require_zero_numeric_compute_processes=True, allow_wddm_graphics_activity=True):
            torch.manual_seed(1612)
            torch.cuda.reset_peak_memory_stats()
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True)
            encoded = [(row, encode_completion_only_sample(row, tokenizer, max_length=384)) for row in read_jsonl(DATA_V23 / "train.jsonl")]
            row, encoding = max(encoded, key=lambda item: len(item[1].input_ids))
            qconfig = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
            started = time.perf_counter()
            model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=True, quantization_config=qconfig, device_map={"": 0}, **{dtype_key: torch.bfloat16})
            model.config.use_cache = False
            model.gradient_checkpointing_enable()
            quantized_module_count = sum(1 for _, module in model.named_modules() if isinstance(module, bnb.nn.Linear4bit))
            model = prepare_model_for_kbit_training(model)
            model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, bias="none", task_type=TaskType.CAUSAL_LM, target_modules=["q_proj", "v_proj"]))
            model_load_ms = (time.perf_counter() - started) * 1000
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
            inputs = {"input_ids": torch.tensor([encoding.input_ids], dtype=torch.long, device="cuda"), "attention_mask": torch.tensor([encoding.attention_mask], dtype=torch.long, device="cuda"), "labels": torch.tensor([encoding.labels], dtype=torch.long, device="cuda")}
            model.train()
            outputs = model(**inputs)
            loss = outputs.loss
            loss_value = float(loss.detach().float().item())
            result["nan"] = int(math.isnan(loss_value))
            result["inf"] = int(math.isinf(loss_value))
            loss.backward()
            gradient_present = any(p.requires_grad and p.grad is not None and torch.isfinite(p.grad).all().item() for p in model.parameters())
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.empty_cache()
            free_mb, util = nvidia_smi()
            peak_memory_mb = torch.cuda.max_memory_allocated() / 1024 / 1024
            result.update({"total_tokens": len(encoding.input_ids), "prompt_tokens": encoding.prompt_token_count, "completion_tokens": encoding.assistant_token_count, "trainable_tokens": sum(1 for label in encoding.labels if label != -100), "loss": loss_value, "gradient_present": bool(gradient_present), "quantized_module_count": quantized_module_count, "model_load_ms": round(model_load_ms, 2), "peak_memory_mb": round(peak_memory_mb, 2), "free_memory_at_peak_mb": free_mb, "gpu_utilization_after_backward": util, "prompt_labels_masked": all(label == -100 for label in encoding.labels[: encoding.prompt_token_count]), "completion_labels_trainable": all(label != -100 for label in encoding.labels[encoding.prompt_token_count :]), "eos_trainable": encoding.eos_token_id in encoding.labels[encoding.prompt_token_count :] if encoding.eos_token_id is not None else False})
            passed = result["prompt_labels_masked"] and result["completion_labels_trainable"] and result["eos_trainable"] and math.isfinite(loss_value) and gradient_present and quantized_module_count > 0 and result["oom"] == 0 and free_mb is not None and free_mb >= 250
            result["status"] = "V23_EXPERIMENT_A_QLORA_BUDGET_PASS" if passed else "V23_EXPERIMENT_A_QLORA_BUDGET_BLOCKED"
            del outputs, loss, inputs, model, tokenizer, optimizer
            model = tokenizer = optimizer = None
            gc.collect()
            torch.cuda.empty_cache()
            if hasattr(torch.cuda, "ipc_collect"):
                torch.cuda.ipc_collect()
    except torch.cuda.OutOfMemoryError as exc:
        result.update({"oom": 1, "error_type": type(exc).__name__})
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error_sanitized": str(exc)[:500]})
    finally:
        gc.collect()
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                if hasattr(torch.cuda, "ipc_collect"):
                    torch.cuda.ipc_collect()
        except Exception:
            pass
        result["gpu_lock_release_success"] = True
    write(result)
    print(result["status"])


def write(result: dict) -> None:
    write_json(AUDIT / "v1612_v23_qlora_budget.json", result)
    write_doc(DOCS / "254_v1612_v23_qlora_budget.md", "V1.6.12 V2.3 QLoRA Budget", [f"Status: `{result['status']}`", f"- total_tokens: `{result.get('total_tokens')}`", f"- loss: `{result.get('loss')}`", f"- peak_memory_mb: `{result.get('peak_memory_mb')}`", f"- free_memory_at_peak_mb: `{result.get('free_memory_at_peak_mb')}`"])


if __name__ == "__main__":
    main()
