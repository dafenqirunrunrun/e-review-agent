from __future__ import annotations

import gc
import json
import os
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "real-model-chain" / "real-llm-smoke-summary.json"

ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_ACTIONS = {"none", "manual-review", "create-risk-task"}
ALLOWED_RISK_TYPES = {"normal_review", "negative_review", "after_sales_risk", "safety_or_fraud_risk", "refund_fraud"}


def main() -> int:
    model_path = Path(os.getenv("AGENT_LLM_MODEL_PATH", r"D:\EReviewAgent\models\v2.2\qwen3-1.7b"))
    started = time.perf_counter()
    result: dict[str, Any] = {
        "modelId": "Qwen/Qwen3-1.7B",
        "pathLabel": model_path.name,
        "provider": "local_qwen3_transformers",
        "fallbackUsed": False,
        "realGenerate": False,
        "cudaUsed": False,
        "enableThinking": False,
        "status": "BLOCKED",
    }
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not model_path.is_dir():
            raise RuntimeError("LLM_MODEL_NOT_FOUND")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA_NOT_AVAILABLE")
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        result["cudaBeforeMb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            local_files_only=True,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=False,
        )
        model.to("cuda")
        model.eval()
        result["modelClass"] = type(model).__name__
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an e-commerce review governance analyst. "
                    "Return one strict JSON object only. Do not output Markdown or explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Review: 用户第七次声称没有收到商品并要求退款，但物流证据 C1 显示本人已签收。"
                    "Evidence C1: 订单签收记录显示收货人本人签收，且地址与订单一致。"
                    "Return exactly one JSON object with these keys and exact enum strings. "
                    "riskLevel must be one of low, medium, high. "
                    "riskTypes must be an array using only refund_fraud or after_sales_risk. "
                    "action must be one of none, manual-review, create-risk-task. "
                    "summary is required and must mention the signed logistics evidence. "
                    "citationIds must be [\"C1\"]. "
                    "abstain and requiresHumanReview must be JSON booleans. "
                    "confidence must be a number from 0 to 1. "
                    "uncertaintyReason must be null or a short string."
                ),
            },
        ]
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer([rendered], return_tensors="pt", truncation=True, max_length=1536)
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        input_tokens = int(inputs["input_ids"].shape[-1])
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=192,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        result["realGenerate"] = True
        output_ids = output[0][input_tokens:]
        text = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
        payload = _extract_json(text)
        validation = _validate_payload(payload)
        result.update(
            {
                "cudaUsed": True,
                "inputTokens": input_tokens,
                "outputTokens": int(output_ids.shape[-1]),
                "rawOutputHash": _stable_hash(text),
                "jsonParsed": True,
                "schemaValid": validation["schemaValid"],
                "validationReasons": validation["reasons"],
                "payloadKeys": sorted(payload.keys()),
                "citationValid": validation["citationValid"],
                "grounded": validation["grounded"],
                "cudaPeakMb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2),
                "tokensPerSecond": round(int(output_ids.shape[-1]) / max(time.perf_counter() - started, 0.001), 3),
            }
        )
        passed = (
            result["modelClass"] == "Qwen3ForCausalLM"
            and result["realGenerate"]
            and result["schemaValid"]
            and result["citationValid"]
            and result["grounded"]
            and not result["fallbackUsed"]
        )
        result["status"] = "PASS" if passed else "FAILED"
        del model
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        result["cudaAfterMb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["errorType"] = type(exc).__name__
        result["error"] = str(exc)[:800]
    result["durationMs"] = round((time.perf_counter() - started) * 1000)
    result["tokens"] = ["AGENT_RAG_V22_REAL_LLM_RUNTIME_PASS"] if result["status"] == "PASS" else ["AGENT_RAG_V22_REAL_LLM_RUNTIME_BLOCKED"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for token in result["tokens"]:
        print(token)
    return 0 if result["status"] == "PASS" else 2


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise RuntimeError("LLM_OUTPUT_JSON_NOT_FOUND")
    return json.loads(match.group(0))


def _validate_payload(payload: dict[str, Any]) -> dict[str, bool]:
    reasons: list[str] = []
    if payload.get("riskLevel") not in ALLOWED_RISK_LEVELS:
        reasons.append("riskLevel")
    if not isinstance(payload.get("riskTypes"), list) or not all(item in ALLOWED_RISK_TYPES for item in payload.get("riskTypes", [])):
        reasons.append("riskTypes")
    if payload.get("action") not in ALLOWED_ACTIONS:
        reasons.append("action")
    if not isinstance(payload.get("summary"), str):
        reasons.append("summary")
    if not isinstance(payload.get("confidence"), (int, float)) or not 0 <= float(payload.get("confidence", -1)) <= 1:
        reasons.append("confidence")
    if not isinstance(payload.get("citationIds"), list):
        reasons.append("citationIds")
    if not isinstance(payload.get("abstain"), bool):
        reasons.append("abstain")
    if not isinstance(payload.get("requiresHumanReview"), bool):
        reasons.append("requiresHumanReview")
    schema_valid = (
        payload.get("riskLevel") in ALLOWED_RISK_LEVELS
        and isinstance(payload.get("riskTypes"), list)
        and all(item in ALLOWED_RISK_TYPES for item in payload.get("riskTypes", []))
        and payload.get("action") in ALLOWED_ACTIONS
        and isinstance(payload.get("summary"), str)
        and isinstance(payload.get("confidence"), (int, float))
        and 0 <= float(payload.get("confidence")) <= 1
        and isinstance(payload.get("citationIds"), list)
        and isinstance(payload.get("abstain"), bool)
        and isinstance(payload.get("requiresHumanReview"), bool)
    )
    citation_valid = set(payload.get("citationIds", [])) <= {"C1"} and bool(payload.get("citationIds"))
    summary = str(payload.get("summary", ""))
    grounded = "签收" in summary or "物流" in summary or "C1" in summary
    return {"schemaValid": schema_valid, "citationValid": citation_valid, "grounded": grounded, "reasons": reasons}


def _stable_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


if __name__ == "__main__":
    raise SystemExit(main())
