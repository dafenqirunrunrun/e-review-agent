from __future__ import annotations

import gc
import json
import math
import os
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "real-model-chain" / "real-reranker-smoke-summary.json"


def main() -> int:
    model_path = Path(os.getenv("RAG_RERANKER_MODEL_PATH", r"D:\EReviewAgent\models\v2.2\bge-reranker-v2-m3"))
    started = time.perf_counter()
    result: dict[str, Any] = {
        "modelId": "BAAI/bge-reranker-v2-m3",
        "pathLabel": model_path.name,
        "effectiveRerankerType": "local-model",
        "fallbackUsed": False,
        "inputCount": 2,
        "outputCount": 0,
        "scoresFinite": False,
        "normalized": True,
        "cudaUsed": False,
        "cudaPeakMb": 0,
        "status": "BLOCKED",
    }
    try:
        import torch
        from FlagEmbedding import FlagReranker

        if not model_path.is_dir():
            raise RuntimeError("RERANKER_MODEL_NOT_FOUND")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            result["cudaBeforeMb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
        model = FlagReranker(str(model_path), use_fp16=True)
        pairs = [
            ["什么是退款欺诈？", "该用户多次声称商品未收到并要求退款，且证据显示签收记录正常。"],
            ["什么是退款欺诈？", "今天天气很好，包装颜色也挺好看。"],
        ]
        scores = model.compute_score(pairs, normalize=True)
        if isinstance(scores, (int, float)):
            scores = [float(scores)]
        scores = [float(item) for item in scores]
        result.update(
            {
                "modelFactory": "FlagReranker",
                "modelClass": type(model).__name__,
                "modelModule": type(model).__module__,
                "scores": scores,
                "outputCount": len(scores),
                "scoresFinite": all(math.isfinite(score) for score in scores),
                "relevantScoreHigher": len(scores) == 2 and scores[0] > scores[1],
                "cudaUsed": bool(torch.cuda.is_available()),
                "cudaPeakMb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 2) if torch.cuda.is_available() else 0,
            }
        )
        passed = (
            result["modelFactory"] == "FlagReranker"
            and result["modelClass"] != "DeterministicReranker"
            and result["outputCount"] == 2
            and result["scoresFinite"]
            and all(0.0 <= score <= 1.0 for score in scores)
            and result["relevantScoreHigher"]
            and not result["fallbackUsed"]
        )
        result["status"] = "PASS" if passed else "FAILED"
        if torch.cuda.is_available():
            del model
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            result["cudaAfterMb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 2)
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["errorType"] = type(exc).__name__
        result["error"] = str(exc)[:500]
    result["durationMs"] = round((time.perf_counter() - started) * 1000)
    result["tokens"] = ["AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS"] if result["status"] == "PASS" else ["AGENT_RAG_V22_REAL_RERANKER_RUNTIME_BLOCKED"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for token in result["tokens"]:
        print(token)
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
