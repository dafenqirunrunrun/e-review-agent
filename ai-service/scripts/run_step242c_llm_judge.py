from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.llm.local_qwen import LocalQwenRuntime, local_qwen_settings
from app.rag_quality.llm_judge import (
    BlindJudgeCase,
    JUDGE_PROTOCOL_VERSION,
    build_blind_prompt,
    judge_agreement,
    model_fingerprint,
    parse_blind_judge_output,
    protocol_hash,
    text_hash,
)
from scripts.build_step242a_rag_quality_v2 import FROZEN_WORKFLOW, FROZEN_WORKFLOW_SHA, load_jsonl, sha256_file


DEFAULT_DATASET = ROOT / "data" / "benchmarks" / "rag_quality_v2" / "dataset_candidate.jsonl"
DEFAULT_OUTPUT = ROOT / "artifacts" / "step242c" / "blind_judge_results.jsonl"
DEFAULT_SUMMARY = ROOT / "artifacts" / "step242c" / "blind_judge_summary.json"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run two label-blind local Qwen review-risk judge passes.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    frozen_sha = sha256_file(FROZEN_WORKFLOW)
    if frozen_sha != FROZEN_WORKFLOW_SHA:
        raise SystemExit(f"STEP242C_FROZEN_WORKFLOW_SHA_MISMATCH actual={frozen_sha}")
    if args.batch_size < 1 or args.batch_size > 10:
        raise SystemExit("STEP242C_BATCH_SIZE_OUT_OF_RANGE")

    dataset_path = args.dataset.resolve()
    output_path = args.output.resolve()
    summary_path = args.summary.resolve()
    cases = load_jsonl(dataset_path)
    expected_ids = [str(item["caseId"]) for item in cases]
    existing = _load_existing(output_path) if args.resume else {}
    pending = [item for item in cases if str(item["caseId"]) not in existing]

    model_dir = args.model_dir.resolve()
    settings = local_qwen_settings()
    settings = type(settings)(
        **{
            **settings.__dict__,
            "model_dir": str(model_dir),
            "device": "cuda",
            "torch_dtype": "bfloat16",
            "max_input_tokens": args.max_input_tokens,
            "max_new_tokens": args.max_new_tokens,
            "enable_thinking": False,
        }
    )
    fingerprint = model_fingerprint(model_dir)
    started = time.perf_counter()
    tokenizer = model = None
    rows = dict(existing)
    try:
        tokenizer, model = LocalQwenRuntime.load(settings)
        for offset in range(0, len(pending), args.batch_size):
            batch = pending[offset : offset + args.batch_size]
            blind_cases = [BlindJudgeCase(str(item["caseId"]), str(item["reviewText"])) for item in batch]
            passes: dict[str, list[dict[str, Any]]] = {}
            raw_hashes: dict[str, str] = {}
            latencies: dict[str, int] = {}
            for pass_name, ordered in (
                ("recall_first", blind_cases),
                ("precision_challenge", list(reversed(blind_cases))),
            ):
                prompt = build_blind_prompt(ordered, pass_name=pass_name)
                raw, latency_ms = _generate(
                    tokenizer,
                    model,
                    prompt,
                    max_input_tokens=args.max_input_tokens,
                    max_new_tokens=args.max_new_tokens,
                )
                try:
                    parsed = parse_blind_judge_output(raw, [item.case_id for item in ordered])
                except ValueError as exc:
                    diagnostic = output_path.parent / "blind_judge_invalid_output.json"
                    diagnostic.parent.mkdir(parents=True, exist_ok=True)
                    diagnostic.write_text(
                        json.dumps(
                            {
                                "passName": pass_name,
                                "caseIds": [item.case_id for item in ordered],
                                "error": str(exc),
                                "rawText": raw,
                                "rawTextHash": text_hash(raw),
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    raise
                passes[pass_name] = parsed
                raw_hashes[pass_name] = text_hash(raw)
                latencies[pass_name] = latency_ms
            first_by = {item["caseId"]: item for item in passes["recall_first"]}
            second_by = {item["caseId"]: item for item in passes["precision_challenge"]}
            for case in blind_cases:
                first = first_by[case.case_id]
                second = second_by[case.case_id]
                rows[case.case_id] = {
                    "schemaVersion": "rag-quality-blind-judge-result-v1",
                    "caseId": case.case_id,
                    "reviewTextHash": text_hash(case.review_text),
                    "judgeA": first,
                    "judgeB": second,
                    "agreement": judge_agreement(first, second),
                    "execution": {
                        "protocolVersion": JUDGE_PROTOCOL_VERSION,
                        "protocolHash": protocol_hash(),
                        "modelId": "Qwen/Qwen3-1.7B",
                        "modelFingerprint": fingerprint,
                        "device": str(next(model.parameters()).device),
                        "dtype": str(next(model.parameters()).dtype).replace("torch.", ""),
                        "deterministicDecoding": True,
                        "candidateLabelsVisible": False,
                        "qrelsVisible": False,
                        "rawOutputHashes": raw_hashes,
                        "latencyMs": latencies,
                    },
                }
            _write_rows(output_path, [rows[case_id] for case_id in expected_ids if case_id in rows])
            print(f"STEP242C_JUDGE_PROGRESS {len(rows)}/{len(cases)}")
    finally:
        LocalQwenRuntime.unload()
        del tokenizer
        del model
        gc.collect()

    ordered_rows = [rows[case_id] for case_id in expected_ids]
    exact_count = sum(item["agreement"]["exact"] for item in ordered_rows)
    low_confidence = sum(item["agreement"]["minimumConfidence"] < 0.75 for item in ordered_rows)
    summary = {
        "schemaVersion": "rag-quality-blind-judge-summary-v1",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "COMPLETE" if len(ordered_rows) == len(cases) else "INCOMPLETE",
        "caseCount": len(ordered_rows),
        "exactAgreementCount": exact_count,
        "exactAgreementRate": round(exact_count / len(ordered_rows), 6) if ordered_rows else 0.0,
        "conflictCount": len(ordered_rows) - exact_count,
        "lowConfidenceCount": low_confidence,
        "protocolVersion": JUDGE_PROTOCOL_VERSION,
        "protocolHash": protocol_hash(),
        "modelId": "Qwen/Qwen3-1.7B",
        "modelFingerprint": fingerprint,
        "datasetPath": str(dataset_path.relative_to(ROOT)).replace("\\", "/"),
        "datasetSha256": sha256_file(dataset_path),
        "frozenWorkflowGoldSha256": frozen_sha,
        "outputSha256": sha256_file(output_path),
        "durationMs": round((time.perf_counter() - started) * 1000),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "COMPLETE" else 1


def _generate(tokenizer, model, prompt: str, *, max_input_tokens: int, max_new_tokens: int) -> tuple[str, int]:
    import torch

    messages = [
        {
            "role": "system",
            "content": "You are a dataset judge. Return one valid JSON object only. No Markdown or chain-of-thought.",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "\n/no_think"
    inputs = tokenizer([rendered], return_tensors="pt", truncation=True, max_length=max_input_tokens)
    device = next(model.parameters()).device
    inputs = {key: value.to(device) for key, value in inputs.items()}
    input_tokens = int(inputs["input_ids"].shape[-1])
    started = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
            pad_token_id=tokenizer.eos_token_id,
        )
    latency_ms = round((time.perf_counter() - started) * 1000)
    output_ids = generated[0][input_tokens:]
    return tokenizer.decode(output_ids, skip_special_tokens=True).strip(), latency_ms


def _load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return {str(item["caseId"]): item for item in load_jsonl(path)}


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rows)
    path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
