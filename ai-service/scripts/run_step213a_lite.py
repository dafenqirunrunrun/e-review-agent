from __future__ import annotations

"""Run the local-only Step 21.3A-Lite Rule Router vs Qwen benchmark."""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.config import ProviderConfig
from app.llm.local_qwen import LocalQwenTransformersProvider, LocalQwenUnavailableError
from app.risk_calibration.severity import BASE_SEVERITY, SeverityRank
from scripts.run_step2123_reliability_analysis import (
    BOUNDARY_SHA,
    CALIBRATION_SHA,
    FROZEN_GOLD_SHA,
    is_material_safety_error,
    load_jsonl,
    percentile,
    safe_ratio,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DATA_DIR = ROOT / "data" / "evaluation_demo"
STEP2123_DIR = ROOT / "artifacts" / "step2123"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213a_lite"
DEFAULT_PROMPT = DEFAULT_OUTPUT_DIR / "local_qwen_router_prompt_v1.md"
DEFAULT_REPORT = REPO_ROOT / "docs" / "LOCAL_QWEN_ROUTER_BENCHMARK_REPORT.md"
DEFAULT_CALIBRATION = DATA_DIR / "router_calibration_candidate_demo_final.jsonl"
DEFAULT_BOUNDARY = DATA_DIR / "boundary_challenge_demo_final.jsonl"
DEFAULT_FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
DEFAULT_SPLIT = STEP2123_DIR / "reliability_split_v1.json"
DEFAULT_RULE_RESULTS = STEP2123_DIR / "router_signal_results_v1.jsonl"

MODEL_PROVIDER_TYPE = "local_qwen3_transformers"
MODEL_NAME = "Qwen/Qwen3-1.7B"
BENCHMARK_VERSION = "step21.3a-lite-local-qwen-router-v1"
MAX_SCHEMA_RETRIES = 1
LATENCY_GUARD_SECONDS = 30.0
GENERATION_CONFIG = {
    "doSample": False,
    "temperature": 0,
    "topP": None,
    "maxNewTokens": 160,
    "maxInputTokens": 2048,
    "enableThinking": False,
}
ALLOWED_RISKS = {
    "normal_review",
    "negative_review",
    "after_sales_risk",
    "fake_review",
    "paid_review",
    "rating_manipulation",
    "review_suppression",
    "safety_or_fraud_risk",
    "harassment_or_abuse",
    "privacy_risk",
}
PROHIBITED_RISKS = {
    "low_confidence",
    "fake_review_suspected",
    "modality_conflict",
    "rating_conflict",
    "other",
}


class LocalRouterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["CLASSIFY", "ABSTAIN"]
    riskTypes: list[
        Literal[
            "normal_review",
            "negative_review",
            "after_sales_risk",
            "fake_review",
            "paid_review",
            "rating_manipulation",
            "review_suppression",
            "safety_or_fraud_risk",
            "harassment_or_abuse",
            "privacy_risk",
        ]
    ] = Field(default_factory=list)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidenceBand: Literal["HIGH", "MEDIUM", "LOW"]
    needsHumanReview: bool
    reasonCodes: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_semantics(self) -> "LocalRouterOutput":
        self.riskTypes = sorted(set(self.riskTypes))
        if self.decision == "ABSTAIN" and self.riskTypes:
            raise ValueError("ABSTAIN_REQUIRES_EMPTY_RISK_TYPES")
        if self.decision == "CLASSIFY" and not self.riskTypes:
            raise ValueError("CLASSIFY_REQUIRES_RISK_TYPE")
        if "normal_review" in self.riskTypes and len(self.riskTypes) > 1:
            raise ValueError("NORMAL_REVIEW_MUST_BE_EXCLUSIVE")
        self.reasonCodes = [normalize_reason_code(value) for value in self.reasonCodes if value.strip()][:12]
        return self


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--phase", choices=("auto", "probe", "full"), default="auto")
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def normalize_reason_code(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return normalized[:64] or "UNSPECIFIED"


def discover_local_model(explicit: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    for name in ("AGENT_LLM_MODEL_PATH", "E_REVIEW_LOCAL_QWEN_MODEL_DIR"):
        if os.getenv(name):
            candidates.append(Path(os.environ[name]))
    candidates.append(ROOT.parents[1] / "models" / "Qwen3-1.7B")
    for candidate in candidates:
        if (candidate / "config.json").is_file() and (
            (candidate / "model.safetensors").is_file()
            or (candidate / "model.safetensors.index.json").is_file()
        ):
            return candidate.resolve()
    raise LocalQwenUnavailableError("LOCAL_QWEN_MODEL_NOT_AVAILABLE")


def model_snapshot(model_dir: Path) -> dict[str, Any]:
    config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    files = sorted(model_dir.glob("*.safetensors"))
    fingerprint_payload = {
        "configSha": sha256_file(model_dir / "config.json"),
        "weights": [{"name": path.name, "size": path.stat().st_size} for path in files],
    }
    return {
        "schemaVersion": "local-qwen-model-snapshot-v1",
        "providerType": MODEL_PROVIDER_TYPE,
        "modelName": MODEL_NAME,
        "modelPathIdentity": "<repo-external>/models/Qwen3-1.7B",
        "modelFingerprint": stable_hash(fingerprint_payload)[:32],
        "parameterSize": "1.7B",
        "architecture": (config.get("architectures") or [None])[0],
        "device": "cpu",
        "dtype": str(config.get("torch_dtype") or "auto"),
        "contextLength": config.get("max_position_embeddings"),
        "generationConfig": GENERATION_CONFIG,
        "localInferenceApiCost": 0,
        "computeCostExcluded": False,
        "externalModelComparison": "NOT_RUN_NO_PROVIDER_CONFIGURED",
    }


def configure_local_provider(model_dir: Path) -> LocalQwenTransformersProvider:
    os.environ["AGENT_LLM_MODEL_PATH"] = str(model_dir)
    os.environ["AGENT_LLM_MODEL_ID"] = MODEL_NAME
    os.environ["AGENT_LLM_DEVICE"] = "cpu"
    os.environ["AGENT_LLM_DTYPE"] = "auto"
    os.environ["AGENT_LLM_MAX_OUTPUT_TOKENS"] = str(GENERATION_CONFIG["maxNewTokens"])
    os.environ["AGENT_LLM_MAX_INPUT_TOKENS"] = str(GENERATION_CONFIG["maxInputTokens"])
    os.environ["AGENT_LLM_ENABLE_THINKING"] = "false"
    return LocalQwenTransformersProvider(
        ProviderConfig(
            provider_name=MODEL_PROVIDER_TYPE,
            base_url="local://transformers",
            model_name=MODEL_NAME,
            api_key_env="",
            timeout_seconds=300,
            max_retries=0,
            enabled=True,
        )
    )


def render_prompt(template: str, review_text: str) -> str:
    if "{{REVIEW_TEXT}}" not in template:
        raise ValueError("PROMPT_REVIEW_PLACEHOLDER_MISSING")
    return template.replace("{{REVIEW_TEXT}}", review_text)


def parse_router_output(raw: str) -> tuple[LocalRouterOutput | None, str | None]:
    try:
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
        cleaned = re.sub(r"^.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise ValueError("JSON_OBJECT_NOT_FOUND")
        return LocalRouterOutput.model_validate(json.loads(cleaned[start : end + 1])), None
    except Exception as exc:
        return None, f"{type(exc).__name__}:{str(exc)[:160]}"


def generation_config_hash() -> str:
    return stable_hash(GENERATION_CONFIG)


def cache_key(*, dataset_hash: str, case_id: str, model_identity: str, prompt_hash: str) -> str:
    return stable_hash(
        {
            "datasetHash": dataset_hash,
            "caseId": case_id,
            "modelIdentity": model_identity,
            "promptHash": prompt_hash,
            "generationConfigHash": generation_config_hash(),
        }
    )


def invoke_local_qwen(
    *,
    provider: Any,
    prompt: str,
    case_id: str,
    dataset_hash: str,
    model_identity: str,
    prompt_hash: str,
    cache_dir: Path,
    use_cache: bool = True,
) -> dict[str, Any]:
    key = cache_key(
        dataset_hash=dataset_hash,
        case_id=case_id,
        model_identity=model_identity,
        prompt_hash=prompt_hash,
    )
    cache_path = cache_dir / f"{key}.json"
    if use_cache and cache_path.is_file():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return {**cached, "cacheHit": True}

    total_latency = 0
    input_tokens = output_tokens = 0
    raw_hashes: list[str] = []
    parsed: LocalRouterOutput | None = None
    error: str | None = None
    retry_count = 0
    current_prompt = prompt
    for attempt in range(MAX_SCHEMA_RETRIES + 1):
        result = provider.complete_json(current_prompt)
        total_latency += int(result.latency_ms or 0)
        input_tokens += int(result.token_usage_input or 0)
        output_tokens += int(result.token_usage_output or 0)
        raw_hashes.append(hashlib.sha256(result.content.encode("utf-8", errors="replace")).hexdigest()[:24])
        parsed, error = parse_router_output(result.content)
        if parsed is not None:
            break
        if attempt < MAX_SCHEMA_RETRIES:
            retry_count += 1
            current_prompt = (
                prompt
                + "\nThe previous response was invalid. Return exactly the requested JSON schema again, with no explanation."
            )

    record = {
        "cacheKey": key,
        "cacheHit": False,
        "schemaValid": parsed is not None,
        "schemaRetryCount": retry_count,
        "latencyMs": total_latency,
        "inputTokens": input_tokens or None,
        "outputTokens": output_tokens or None,
        "rawOutputHashes": raw_hashes,
        "output": parsed.model_dump() if parsed else None,
        "errorCode": None if parsed else "LOCAL_QWEN_SCHEMA_INVALID",
        "errorSummary": error,
    }
    if use_cache:
        write_json(cache_path, record)
    return record


def expected_risks(case: dict[str, Any]) -> list[str]:
    value = case.get("benchmarkRiskTypes")
    return sorted(set(case.get("riskTypes", []) if value is None else value))


def select_probe_cases(validation: list[dict[str, Any]], boundary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selectors: list[tuple[str, list[dict[str, Any]], Callable[[dict[str, Any]], bool]]] = [
        ("normal", validation, lambda row: expected_risks(row) == ["normal_review"]),
        ("implicit", validation, lambda row: row.get("expressionType") == "implicit" and expected_risks(row) != ["normal_review"]),
        ("multi-risk", boundary, lambda row: bool(row.get("multiRisk")) and row.get("evaluationTarget") != "ABSTENTION"),
        ("hard-negative", boundary, lambda row: row.get("boundaryType") == "hard_negative"),
        ("ambiguous", boundary, lambda row: row.get("evaluationTarget") == "ABSTENTION"),
    ]
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for probe_type, rows, predicate in selectors:
        candidates = sorted((row for row in rows if predicate(row) and row["caseId"] not in used), key=lambda row: row["caseId"])
        if not candidates:
            raise ValueError(f"PROBE_SLICE_EMPTY:{probe_type}")
        chosen = dict(candidates[0])
        chosen["probeType"] = probe_type
        selected.append(chosen)
        used.add(chosen["caseId"])
    return selected


def evaluate_output(case: dict[str, Any], inference: dict[str, Any], rule_signal: dict[str, Any]) -> dict[str, Any]:
    target = str(case.get("evaluationTarget") or "RISK_CLASSIFICATION").upper()
    expected = expected_risks(case)
    output = inference.get("output") or {}
    predicted = sorted(set(output.get("riskTypes") or []))
    decision = output.get("decision")
    confidence = output.get("confidenceBand")
    exact = target != "ABSTENTION" and predicted == expected
    abstention_correct = target == "ABSTENTION" and (
        decision == "ABSTAIN"
        or bool(output.get("needsHumanReview")) and confidence in {"LOW", "MEDIUM"}
    )
    false_confident = target == "ABSTENTION" and decision == "CLASSIFY" and confidence == "HIGH"
    material_error, missing_material = is_material_safety_error(expected, predicted)
    expected_set, predicted_set = set(expected), set(predicted)
    tp = len(expected_set & predicted_set)
    precision = safe_ratio(tp, len(predicted_set)) if target != "ABSTENTION" else None
    recall = safe_ratio(tp, len(expected_set)) if target != "ABSTENTION" else None
    f1 = safe_ratio(2 * precision * recall, precision + recall) if precision is not None and recall is not None and precision + recall else (0.0 if target != "ABSTENTION" else None)
    auto_pass_candidate = bool(
        material_error
        and decision == "CLASSIFY"
        and confidence == "HIGH"
        and not output.get("needsHumanReview")
    )
    return {
        "schemaVersion": "local-qwen-router-output-v1",
        "caseId": case["caseId"],
        "datasetPartition": "CALIBRATION_VALIDATION" if case.get("_partition") == "VALIDATION" else "BOUNDARY_CHALLENGE",
        "probeType": case.get("probeType"),
        "evaluationTarget": target,
        "expectedRiskTypes": expected,
        "sourceDataset": case.get("sourceDataset"),
        "expressionType": case.get("expressionType"),
        "difficulty": case.get("difficulty"),
        "multiRisk": bool(case.get("multiRisk")),
        "boundaryType": case.get("boundaryType"),
        "schemaValid": inference["schemaValid"],
        "schemaRetryCount": inference["schemaRetryCount"],
        "cacheHit": inference["cacheHit"],
        "latencyMs": inference["latencyMs"],
        "inputTokens": inference["inputTokens"],
        "outputTokens": inference["outputTokens"],
        "output": output or None,
        "rawOutputHashes": inference["rawOutputHashes"],
        "errorCode": inference["errorCode"],
        "exactMatch": exact,
        "riskTypePrecision": precision,
        "riskTypeRecall": recall,
        "riskTypeF1": f1,
        "abstentionCorrect": abstention_correct,
        "falseConfidentClassification": false_confident,
        "outcomeCorrect": exact or abstention_correct,
        "materialSafetyError": material_error,
        "missingMaterialRiskTypes": missing_material,
        "highRiskMiss": material_error,
        "highRiskAutoPassCandidate": auto_pass_candidate,
        "safetyGateTriggered": bool(rule_signal.get("safetyGateTriggered")),
    }


def multilabel_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scoped = [row for row in rows if row["evaluationTarget"] != "ABSTENTION"]
    labels = sorted({risk for row in scoped for risk in row["expectedRiskTypes"] + ((row.get("output") or {}).get("riskTypes") or [])})
    total_tp = total_fp = total_fn = 0
    per_label: dict[str, Any] = {}
    for label in labels:
        tp = sum(label in row["expectedRiskTypes"] and label in ((row.get("output") or {}).get("riskTypes") or []) for row in scoped)
        fp = sum(label not in row["expectedRiskTypes"] and label in ((row.get("output") or {}).get("riskTypes") or []) for row in scoped)
        fn = sum(label in row["expectedRiskTypes"] and label not in ((row.get("output") or {}).get("riskTypes") or []) for row in scoped)
        precision = safe_ratio(tp, tp + fp)
        recall = safe_ratio(tp, tp + fn)
        f1 = safe_ratio(2 * precision * recall, precision + recall)
        per_label[label] = {"support": tp + fn, "precision": precision, "recall": recall, "f1": f1}
        total_tp += tp
        total_fp += fp
        total_fn += fn
    micro_precision = safe_ratio(total_tp, total_tp + total_fp)
    micro_recall = safe_ratio(total_tp, total_tp + total_fn)
    micro_f1 = safe_ratio(2 * micro_precision * micro_recall, micro_precision + micro_recall)
    return {
        "caseCount": len(scoped),
        "exactSetMatchAccuracy": safe_ratio(sum(row["exactMatch"] for row in scoped), len(scoped)),
        "microPrecision": micro_precision,
        "microRecall": micro_recall,
        "microF1": micro_f1,
        "macroF1": round(sum(item["f1"] for item in per_label.values()) / len(per_label), 6) if per_label else 0.0,
        "perLabel": per_label,
    }


def slice_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = multilabel_metrics(rows)
    return {"caseCount": len(rows), "exactAccuracy": metrics["exactSetMatchAccuracy"], "microF1": metrics["microF1"]}


def quality_metrics(rows: list[dict[str, Any]], *, completed: bool, stop_reason: str | None = None) -> dict[str, Any]:
    base = multilabel_metrics(rows)
    classification_case_count = base.pop("caseCount")
    selectors = {
        "normalReview": lambda row: row["expectedRiskTypes"] == ["normal_review"],
        "singleRisk": lambda row: len(row["expectedRiskTypes"]) == 1 and row["evaluationTarget"] != "ABSTENTION",
        "multiRisk": lambda row: bool(row["multiRisk"]),
        "hard": lambda row: row["difficulty"] == "hard" and row["evaluationTarget"] != "ABSTENTION",
    }
    boundary_types = sorted({row["boundaryType"] for row in rows if row.get("boundaryType")})
    return {
        "schemaVersion": "local-qwen-quality-metrics-v1",
        "benchmarkCompleted": completed,
        "stopReason": stop_reason,
        "caseCount": len(rows),
        "classificationCaseCount": classification_case_count,
        **base,
        "slices": {name: slice_summary([row for row in rows if selector(row)]) for name, selector in selectors.items()},
        "boundary": {
            "overall": slice_summary([row for row in rows if row["datasetPartition"] == "BOUNDARY_CHALLENGE"]),
            "byType": {kind: slice_summary([row for row in rows if row["boundaryType"] == kind]) for kind in boundary_types},
        },
        "abstention": {
            "caseCount": sum(row["evaluationTarget"] == "ABSTENTION" for row in rows),
            "accuracy": safe_ratio(
                sum(row["abstentionCorrect"] for row in rows if row["evaluationTarget"] == "ABSTENTION"),
                sum(row["evaluationTarget"] == "ABSTENTION" for row in rows),
            ),
            "falseConfidentClassificationCount": sum(row["falseConfidentClassification"] for row in rows),
            "overAbstentionRate": safe_ratio(
                sum((row.get("output") or {}).get("decision") == "ABSTAIN" for row in rows if row["evaluationTarget"] != "ABSTENTION"),
                sum(row["evaluationTarget"] != "ABSTENTION" for row in rows),
            ),
        },
        "schemaCompliance": safe_ratio(sum(row["schemaValid"] for row in rows), len(rows)),
    }


def latency_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["latencyMs"]) for row in rows]
    return {
        "count": len(values),
        "p50Ms": percentile(values, 0.50),
        "p95Ms": percentile(values, 0.95),
        "p99Ms": percentile(values, 0.99),
    }


def safety_metrics(rows: list[dict[str, Any]], *, official: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "local-qwen-safety-metrics-v1",
        "officialBenchmark": official,
        "caseCount": len(rows),
        "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in rows),
        "highRiskMissCount": sum(row["highRiskMiss"] for row in rows),
        "highRiskAutoPassCandidateCount": sum(row["highRiskAutoPassCandidate"] for row in rows),
    }


def reliability_tier(row: dict[str, Any]) -> str:
    output = row.get("output") or {}
    if not row.get("schemaValid"):
        return "LOW_RELIABILITY"
    if output.get("decision") == "ABSTAIN":
        return "ABSTAIN"
    if (
        output.get("confidenceBand") == "HIGH"
        and not output.get("needsHumanReview")
        and output.get("severity") in {"LOW", "MEDIUM"}
        and not row.get("safetyGateTriggered")
    ):
        return "HIGH_RELIABILITY"
    if output.get("confidenceBand") in {"HIGH", "MEDIUM"}:
        return "MEDIUM_RELIABILITY"
    return "LOW_RELIABILITY"


def reliability_metrics(rows: list[dict[str, Any]], *, official: bool) -> dict[str, Any]:
    confidence: dict[str, Any] = {}
    for band in ("HIGH", "MEDIUM", "LOW"):
        group = [row for row in rows if (row.get("output") or {}).get("confidenceBand") == band]
        confidence[band] = {
            "count": len(group),
            "coverage": safe_ratio(len(group), len(rows)),
            "accuracy": safe_ratio(sum(row["outcomeCorrect"] for row in group), len(group)) if group else None,
            "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in group),
        }
    nonempty = [confidence[band]["accuracy"] for band in ("HIGH", "MEDIUM", "LOW") if confidence[band]["accuracy"] is not None]
    monotonic = len(nonempty) == 3 and nonempty[0] > nonempty[1] > nonempty[2]
    tiers: dict[str, Any] = {}
    for tier in ("HIGH_RELIABILITY", "MEDIUM_RELIABILITY", "LOW_RELIABILITY", "ABSTAIN"):
        group = [row for row in rows if reliability_tier(row) == tier]
        tiers[tier] = {
            "count": len(group),
            "coverage": safe_ratio(len(group), len(rows)),
            "accuracy": safe_ratio(sum(row["outcomeCorrect"] for row in group), len(group)) if group else None,
            "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in group),
        }
    high = tiers["HIGH_RELIABILITY"]
    fast_pass = bool(
        official
        and high["count"]
        and high["coverage"] >= 0.10
        and float(high["accuracy"] or 0) >= 0.95
        and high["materialSafetyErrorCount"] == 0
    )
    return {
        "schemaVersion": "local-qwen-reliability-metrics-v1",
        "officialBenchmark": official,
        "selfReportedConfidence": confidence,
        "confidenceMonotonic": monotonic,
        "confidenceFinding": "PASS" if monotonic else "SELF_REPORTED_CONFIDENCE_NOT_RELIABLE",
        "reliabilityTiers": tiers,
        "fastPathCandidateGate": "PASS" if fast_pass else "FAIL",
    }


def rule_baseline(rule_rows: list[dict[str, Any]]) -> dict[str, Any]:
    classification = [row for row in rule_rows if row["evaluationTarget"] != "ABSTENTION"]
    labels = sorted({risk for row in classification for risk in row["expectedRiskTypes"] + row["predictedRiskTypes"]})
    tp = fp = fn = 0
    per_f1 = []
    for label in labels:
        ltp = sum(label in row["expectedRiskTypes"] and label in row["predictedRiskTypes"] for row in classification)
        lfp = sum(label not in row["expectedRiskTypes"] and label in row["predictedRiskTypes"] for row in classification)
        lfn = sum(label in row["expectedRiskTypes"] and label not in row["predictedRiskTypes"] for row in classification)
        precision, recall = safe_ratio(ltp, ltp + lfp), safe_ratio(ltp, ltp + lfn)
        per_f1.append(safe_ratio(2 * precision * recall, precision + recall))
        tp += ltp
        fp += lfp
        fn += lfn
    precision, recall = safe_ratio(tp, tp + fp), safe_ratio(tp, tp + fn)
    micro_f1 = safe_ratio(2 * precision * recall, precision + recall)
    multi = [row for row in classification if row["multiRisk"]]
    hard = [row for row in classification if row["difficulty"] == "hard"]
    boundary = [row for row in classification if row["datasetPartition"] == "BOUNDARY_CHALLENGE"]
    abstention = [row for row in rule_rows if row["evaluationTarget"] == "ABSTENTION"]
    return {
        "caseCount": len(rule_rows),
        "exactSetMatchAccuracy": safe_ratio(sum(row["exactMatch"] for row in classification), len(classification)),
        "microF1": micro_f1,
        "macroF1": round(sum(per_f1) / len(per_f1), 6),
        "multiRiskExactAccuracy": safe_ratio(sum(row["exactMatch"] for row in multi), len(multi)),
        "multiRiskMicroF1": rule_subset_f1(multi),
        "hardAccuracy": safe_ratio(sum(row["exactMatch"] for row in hard), len(hard)),
        "boundaryAccuracy": safe_ratio(sum(row["exactMatch"] for row in boundary), len(boundary)),
        "boundaryMicroF1": rule_subset_f1(boundary),
        "abstentionAccuracy": safe_ratio(sum(row["abstentionCorrect"] for row in abstention), len(abstention)),
        "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in rule_rows),
        "highRiskMissCount": sum(row["materialSafetyError"] for row in rule_rows),
        "schemaCompliance": 1.0,
        "latency": latency_metrics(rule_rows),
    }


def rule_subset_f1(rows: list[dict[str, Any]]) -> float:
    tp = fp = fn = 0
    for row in rows:
        expected, predicted = set(row["expectedRiskTypes"]), set(row["predictedRiskTypes"])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    precision, recall = safe_ratio(tp, tp + fp), safe_ratio(tp, tp + fn)
    return safe_ratio(2 * precision * recall, precision + recall)


def comparison_artifact(rule: dict[str, Any], qwen: dict[str, Any] | None, *, completed: bool) -> dict[str, Any]:
    qwen_values = None
    improvements = None
    if qwen is not None:
        qwen_values = {
            "exactSetMatchAccuracy": qwen["exactSetMatchAccuracy"],
            "microF1": qwen["microF1"],
            "macroF1": qwen["macroF1"],
            "multiRiskExactAccuracy": qwen["slices"]["multiRisk"]["exactAccuracy"],
            "multiRiskMicroF1": qwen["slices"]["multiRisk"]["microF1"],
            "hardAccuracy": qwen["slices"]["hard"]["exactAccuracy"],
            "boundaryAccuracy": qwen["boundary"]["overall"]["exactAccuracy"],
            "boundaryMicroF1": qwen["boundary"]["overall"]["microF1"],
            "abstentionAccuracy": qwen["abstention"]["accuracy"],
            "schemaCompliance": qwen["schemaCompliance"],
        }
        rule_error = 1 - rule["exactSetMatchAccuracy"]
        qwen_error = 1 - qwen_values["exactSetMatchAccuracy"]
        improvements = {
            "absoluteAccuracyGain": round(qwen_values["exactSetMatchAccuracy"] - rule["exactSetMatchAccuracy"], 6),
            "relativeErrorReduction": round((rule_error - qwen_error) / rule_error, 6) if rule_error else 0.0,
            "microF1Gain": round(qwen_values["microF1"] - rule["microF1"], 6),
            "boundaryF1Gain": round(qwen_values["boundaryMicroF1"] - rule["boundaryMicroF1"], 6),
            "multiRiskF1Gain": round(qwen_values["multiRiskMicroF1"] - rule["multiRiskMicroF1"], 6),
        }
    return {
        "schemaVersion": "rule-vs-local-qwen-comparison-v1",
        "comparisonCompleted": completed,
        "ruleBaselineSource": "Step21.2.3 immutable router_signal_results_v1.jsonl",
        "rule": rule,
        "localQwen": qwen_values,
        "improvements": improvements,
    }


def build_report(
    snapshot: dict[str, Any],
    availability: dict[str, Any],
    probe: dict[str, Any],
    quality: dict[str, Any],
    safety: dict[str, Any],
    reliability: dict[str, Any],
    comparison: dict[str, Any],
    gate: dict[str, Any],
) -> str:
    rule = comparison["rule"]
    qwen = comparison.get("localQwen")

    def qwen_metric(name: str) -> str:
        return "N/A" if qwen is None else f"{qwen[name]:.4f}"

    lines = [
        "# Local Qwen Router Benchmark Report",
        "",
        "## Scope",
        "",
        "Step 21.3A-Lite compares the immutable Step 21.2.3 Rule Router baseline with the existing local Qwen generation model. It does not modify runtime routing, execute Frozen Gold, use RAG, or call an external model provider.",
        "",
        "## Local Model",
        "",
        f"- Provider: `{snapshot['providerType']}`",
        f"- Model: `{snapshot['modelName']}` ({snapshot['parameterSize']})",
        f"- Device / dtype: `{snapshot['device']}` / `{snapshot['dtype']}`",
        f"- Context length: `{snapshot['contextLength']}`",
        "- External API cost: `0`; local compute, latency, and hardware cost are not zero.",
        "",
        "## Availability",
        "",
        f"Gate: `{gate['localQwenAvailabilityGate']}`. Schema valid: `{availability['schemaValid']}`. Latency: `{availability['latencyMs']} ms`.",
        "",
        "## Five Case Latency Probe",
        "",
        f"P50 `{probe['latency']['p50Ms']} ms`, P95 `{probe['latency']['p95Ms']} ms`, P99 `{probe['latency']['p99Ms']} ms`. Status: `{probe['status']}`.",
        "",
        "## Benchmark Execution",
        "",
        f"Completed cases: `{quality['caseCount']}`. Full 100-case benchmark completed: `{quality['benchmarkCompleted']}`. Stop reason: `{quality.get('stopReason')}`.",
        "",
        "## Rule vs Local Qwen",
        "",
        "| Metric | Rule | Local Qwen |",
        "| --- | ---: | ---: |",
        f"| Exact Accuracy | {rule['exactSetMatchAccuracy']:.4f} | {qwen_metric('exactSetMatchAccuracy')} |",
        f"| Micro F1 | {rule['microF1']:.4f} | {qwen_metric('microF1')} |",
        f"| Macro F1 | {rule['macroF1']:.4f} | {qwen_metric('macroF1')} |",
        f"| Multi-risk Exact | {rule['multiRiskExactAccuracy']:.4f} | {qwen_metric('multiRiskExactAccuracy')} |",
        f"| Multi-risk F1 | {rule['multiRiskMicroF1']:.4f} | {qwen_metric('multiRiskMicroF1')} |",
        f"| Boundary Accuracy | {rule['boundaryAccuracy']:.4f} | {qwen_metric('boundaryAccuracy')} |",
        f"| Boundary F1 | {rule['boundaryMicroF1']:.4f} | {qwen_metric('boundaryMicroF1')} |",
        f"| Abstention Accuracy | {rule['abstentionAccuracy']:.4f} | {qwen_metric('abstentionAccuracy')} |",
        f"| Material Safety Errors | {rule['materialSafetyErrorCount']} | {('N/A' if not quality['benchmarkCompleted'] else safety['materialSafetyErrorCount'])} |",
        f"| Schema Compliance | {rule['schemaCompliance']:.4f} | {quality['schemaCompliance']:.4f} |",
        f"| P50 ms | {rule['latency']['p50Ms']} | {probe['latency']['p50Ms']} |",
        f"| P95 ms | {rule['latency']['p95Ms']} | {probe['latency']['p95Ms']} |",
        "",
        "Probe-only Qwen quality values are intentionally not promoted into the official comparison when the CPU latency guard stops the 100-case run.",
        "",
        "## Reliability",
        "",
        f"Self-reported confidence finding: `{reliability['confidenceFinding']}`. Fast-path candidate gate: `{reliability['fastPathCandidateGate']}`.",
        "",
        "## Safety",
        "",
        f"Official safety benchmark: `{safety['officialBenchmark']}`. Probe material safety errors: `{safety['materialSafetyErrorCount']}`. High-risk auto-pass candidates: `{safety['highRiskAutoPassCandidateCount']}`.",
        "",
        "## Cost and External Models",
        "",
        "`LOCAL_INFERENCE_API_COST = 0`. This excludes local compute, latency, and hardware cost. `EXTERNAL_MODEL_COMPARISON = NOT_RUN_NO_PROVIDER_CONFIGURED`.",
        "",
        "## Gates",
        "",
        *(f"- `{key}` = `{value}`" for key, value in gate.items() if key.endswith("Gate")),
        "",
        "## Frozen Gold",
        "",
        f"Frozen Gold was not executed. SHA remained `{FROZEN_GOLD_SHA}`.",
        "",
        "## Limitations",
        "",
        "- The local Python environment is CPU-only even though the host has a discrete GPU.",
        "- The Demo Candidate dataset is not human gold.",
        "- A five-case latency probe is not a quality benchmark.",
        "- No external model comparison was run.",
        "",
        "## Next Recommendation",
        "",
        f"`{gate['nextRecommendation']}`",
        "",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    protected = [DEFAULT_CALIBRATION, DEFAULT_BOUNDARY, DEFAULT_FROZEN, DEFAULT_SPLIT, DEFAULT_RULE_RESULTS]
    before = {str(path): sha256_file(path) for path in protected}
    if before[str(DEFAULT_CALIBRATION)] != CALIBRATION_SHA:
        raise SystemExit("CALIBRATION_DATASET_HASH_MISMATCH")
    if before[str(DEFAULT_BOUNDARY)] != BOUNDARY_SHA:
        raise SystemExit("BOUNDARY_DATASET_HASH_MISMATCH")
    if before[str(DEFAULT_FROZEN)] != FROZEN_GOLD_SHA:
        raise SystemExit("FROZEN_GOLD_HASH_MISMATCH")

    model_dir = discover_local_model(args.model_dir)
    snapshot = model_snapshot(model_dir)
    prompt_template = args.prompt.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(args.prompt.read_bytes()).hexdigest().upper()
    snapshot.update({"promptHash": prompt_hash, "generationConfigHash": generation_config_hash()})
    provider = configure_local_provider(model_dir)
    cache_dir = args.output_dir / "cache"

    split = json.loads(DEFAULT_SPLIT.read_text(encoding="utf-8"))
    validation_ids = {row["caseId"] for row in split["rows"] if row["partition"] == "VALIDATION"}
    calibration = [dict(row, _partition="VALIDATION") for row in load_jsonl(DEFAULT_CALIBRATION) if row["caseId"] in validation_ids]
    boundary = [dict(row, _partition="BOUNDARY_CHALLENGE") for row in load_jsonl(DEFAULT_BOUNDARY)]
    if len(calibration) != 40 or len(boundary) != 60:
        raise SystemExit("BENCHMARK_CASE_COUNT_MISMATCH")
    rule_rows = [
        row for row in load_jsonl(DEFAULT_RULE_RESULTS)
        if row["partition"] in {"VALIDATION", "BOUNDARY_CHALLENGE"}
    ]
    if len(rule_rows) != 100:
        raise SystemExit("RULE_BASELINE_COUNT_MISMATCH")
    rule_by_id = {row["caseId"]: row for row in rule_rows}
    rule_metrics = rule_baseline(rule_rows)

    smoke_prompt = render_prompt(prompt_template, "商品与描述一致，使用正常。")
    smoke = invoke_local_qwen(
        provider=provider,
        prompt=smoke_prompt,
        case_id="step213a-lite-availability-smoke",
        dataset_hash="AVAILABILITY_SMOKE_V1",
        model_identity=snapshot["modelFingerprint"],
        prompt_hash=prompt_hash,
        cache_dir=cache_dir,
        use_cache=False,
    )
    availability_pass = bool(smoke["schemaValid"])
    availability = {
        "success": availability_pass,
        "schemaValid": smoke["schemaValid"],
        "latencyMs": smoke["latencyMs"],
        "schemaRetryCount": smoke["schemaRetryCount"],
        "inputTokens": smoke["inputTokens"],
        "outputTokens": smoke["outputTokens"],
        "errorCode": smoke["errorCode"],
    }
    if not availability_pass:
        result = finalize_partial(args, snapshot, availability, [], rule_metrics, "LOCAL_QWEN_AVAILABILITY_FAILED")
        assert_protected_unchanged(before)
        return result

    probes = select_probe_cases(calibration, boundary)
    probe_rows: list[dict[str, Any]] = []
    for case in probes:
        dataset_hash = CALIBRATION_SHA if case["_partition"] == "VALIDATION" else BOUNDARY_SHA
        inference = invoke_local_qwen(
            provider=provider,
            prompt=render_prompt(prompt_template, case["textZh"]),
            case_id=case["caseId"],
            dataset_hash=dataset_hash,
            model_identity=snapshot["modelFingerprint"],
            prompt_hash=prompt_hash,
            cache_dir=cache_dir,
        )
        probe_rows.append(evaluate_output(case, inference, rule_by_id[case["caseId"]]))
        write_jsonl(args.output_dir / "local_qwen_router_outputs_v1.jsonl", probe_rows)

    probe_latency = latency_metrics(probe_rows)
    high_latency = float(probe_latency["p50Ms"]) > LATENCY_GUARD_SECONDS * 1000
    if args.phase in {"auto", "probe"} and high_latency:
        result = finalize_partial(args, snapshot, availability, probe_rows, rule_metrics, "LOCAL_QWEN_HIGH_LATENCY")
        assert_protected_unchanged(before)
        return result
    if args.phase == "probe":
        result = finalize_partial(args, snapshot, availability, probe_rows, rule_metrics, "PROBE_ONLY_REQUESTED")
        assert_protected_unchanged(before)
        return result

    all_cases = calibration + boundary
    rows_by_id = {row["caseId"]: row for row in probe_rows}
    for case in all_cases:
        if case["caseId"] in rows_by_id:
            continue
        dataset_hash = CALIBRATION_SHA if case["_partition"] == "VALIDATION" else BOUNDARY_SHA
        inference = invoke_local_qwen(
            provider=provider,
            prompt=render_prompt(prompt_template, case["textZh"]),
            case_id=case["caseId"],
            dataset_hash=dataset_hash,
            model_identity=snapshot["modelFingerprint"],
            prompt_hash=prompt_hash,
            cache_dir=cache_dir,
        )
        rows_by_id[case["caseId"]] = evaluate_output(case, inference, rule_by_id[case["caseId"]])
        write_jsonl(args.output_dir / "local_qwen_router_outputs_v1.jsonl", [rows_by_id[item["caseId"]] for item in all_cases if item["caseId"] in rows_by_id])
    rows = [rows_by_id[case["caseId"]] for case in all_cases]
    result = finalize_complete(args, snapshot, availability, rows, rule_metrics, provider, prompt_template, prompt_hash, all_cases, rule_by_id)
    assert_protected_unchanged(before)
    return result


def finalize_partial(
    args: argparse.Namespace,
    snapshot: dict[str, Any],
    availability: dict[str, Any],
    rows: list[dict[str, Any]],
    rule: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    quality = quality_metrics(rows, completed=False, stop_reason=reason)
    safety = safety_metrics(rows, official=False)
    reliability = reliability_metrics(rows, official=False)
    probe_latency = latency_metrics(rows)
    probe = {
        "caseCount": len(rows),
        "status": reason,
        "latency": probe_latency,
        "estimated100CaseMinutesAtP50": round(float(probe_latency["p50Ms"]) * 100 / 60000, 2) if rows else None,
    }
    comparison = comparison_artifact(rule, None, completed=False)
    gate = {
        "benchmarkHarnessGate": "PASS",
        "localQwenAvailabilityGate": "PASS" if availability["success"] else "FAIL",
        "localQwenQualityGate": "FAIL",
        "localQwenReliabilityGate": "FAIL",
        "ruleVsQwenComparisonGate": "FAIL",
        "externalModelComparisonGate": "NOT_RUN_NO_PROVIDER_CONFIGURED",
        "step21_3aLiteGate": "FAIL",
        "primaryReasonCode": reason,
        "fullBenchmarkCompleted": False,
        "frozenBenchmarkExecuted": False,
        "nextRecommendation": "LOCAL_QWEN_NOT_SUITABLE_AS_ROUTER",
    }
    write_outputs(args, snapshot, availability, probe, quality, safety, reliability, comparison, gate, rows)
    return {"model": snapshot, "availability": availability, "probe": probe, "gate": gate}


def finalize_complete(
    args: argparse.Namespace,
    snapshot: dict[str, Any],
    availability: dict[str, Any],
    rows: list[dict[str, Any]],
    rule: dict[str, Any],
    provider: Any,
    prompt_template: str,
    prompt_hash: str,
    all_cases: list[dict[str, Any]],
    rule_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    quality = quality_metrics(rows, completed=True)
    safety = safety_metrics(rows, official=True)
    reliability = reliability_metrics(rows, official=True)
    comparison = comparison_artifact(rule, quality, completed=True)
    comparison["localQwen"]["materialSafetyErrorCount"] = safety["materialSafetyErrorCount"]
    comparison["localQwen"]["highRiskMissCount"] = safety["highRiskMissCount"]
    comparison["localQwen"]["latency"] = latency_metrics(rows)
    comparison["improvements"]["materialSafetyErrorReduction"] = rule["materialSafetyErrorCount"] - safety["materialSafetyErrorCount"]
    general_pass = quality["microF1"] >= 0.80 and quality["boundary"]["overall"]["microF1"] >= 0.75 and quality["slices"]["multiRisk"]["microF1"] >= 0.75 and safety["materialSafetyErrorCount"] < rule["materialSafetyErrorCount"]
    large_gain = comparison["improvements"]["microF1Gain"] >= 0.20 and safety["materialSafetyErrorCount"] < rule["materialSafetyErrorCount"]
    quality_gate = "PASS" if general_pass else ("PASS_WITH_LIMITATIONS" if large_gain else "FAIL")
    reliability_gate = "PASS" if reliability["fastPathCandidateGate"] == "PASS" else "FAIL"
    recommendation = (
        "DESIGN_LOCAL_QWEN_ROUTER_SIMULATION"
        if general_pass and reliability_gate == "PASS"
        else "NEED_STRONGER_ROUTER_FOR_ESCALATION"
        if large_gain
        else "LOCAL_QWEN_NOT_SUITABLE_AS_ROUTER"
    )
    stability_cases = sorted(all_cases, key=lambda row: stable_hash(row["caseId"]))[:10]
    stable_risk = stable_decision = 0
    original_by_id = {row["caseId"]: row for row in rows}
    for case in stability_cases:
        dataset_hash = CALIBRATION_SHA if case["_partition"] == "VALIDATION" else BOUNDARY_SHA
        repeated = invoke_local_qwen(
            provider=provider,
            prompt=render_prompt(prompt_template, case["textZh"]),
            case_id=case["caseId"] + "-stability-repeat",
            dataset_hash=dataset_hash,
            model_identity=snapshot["modelFingerprint"],
            prompt_hash=prompt_hash,
            cache_dir=args.output_dir / "cache",
            use_cache=False,
        )
        evaluated = evaluate_output(case, repeated, rule_by_id[case["caseId"]])
        original = original_by_id[case["caseId"]].get("output") or {}
        repeat_output = evaluated.get("output") or {}
        stable_risk += set(original.get("riskTypes") or []) == set(repeat_output.get("riskTypes") or [])
        stable_decision += original.get("decision") == repeat_output.get("decision")
    quality["stability"] = {
        "caseCount": len(stability_cases),
        "riskTypeStability": safe_ratio(stable_risk, len(stability_cases)),
        "decisionStability": safe_ratio(stable_decision, len(stability_cases)),
    }
    probe_rows = [row for row in rows if row.get("probeType")]
    probe = {"caseCount": len(probe_rows), "status": "PASS", "latency": latency_metrics(probe_rows), "estimated100CaseMinutesAtP50": None}
    gate = {
        "benchmarkHarnessGate": "PASS",
        "localQwenAvailabilityGate": "PASS",
        "localQwenQualityGate": quality_gate,
        "localQwenReliabilityGate": reliability_gate,
        "ruleVsQwenComparisonGate": "PASS",
        "externalModelComparisonGate": "NOT_RUN_NO_PROVIDER_CONFIGURED",
        "step21_3aLiteGate": "PASS",
        "primaryReasonCode": None,
        "fullBenchmarkCompleted": True,
        "frozenBenchmarkExecuted": False,
        "nextRecommendation": recommendation,
    }
    write_outputs(args, snapshot, availability, probe, quality, safety, reliability, comparison, gate, rows)
    return {"model": snapshot, "availability": availability, "probe": probe, "quality": quality, "comparison": comparison, "gate": gate}


def write_outputs(
    args: argparse.Namespace,
    snapshot: dict[str, Any],
    availability: dict[str, Any],
    probe: dict[str, Any],
    quality: dict[str, Any],
    safety: dict[str, Any],
    reliability: dict[str, Any],
    comparison: dict[str, Any],
    gate: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    snapshot = {**snapshot, "availability": availability, "latencyProbe": probe}
    write_json(args.output_dir / "local_qwen_model_snapshot_v1.json", snapshot)
    write_jsonl(args.output_dir / "local_qwen_router_outputs_v1.jsonl", rows)
    write_json(args.output_dir / "local_qwen_quality_metrics_v1.json", quality)
    write_json(args.output_dir / "local_qwen_safety_metrics_v1.json", safety)
    write_json(args.output_dir / "local_qwen_reliability_metrics_v1.json", reliability)
    write_json(args.output_dir / "rule_vs_local_qwen_comparison_v1.json", comparison)
    write_json(args.output_dir / "step213a_lite_gate_v1.json", gate)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(snapshot, availability, probe, quality, safety, reliability, comparison, gate), encoding="utf-8", newline="\n")


def assert_protected_unchanged(expected_hashes: dict[str, str] | None = None) -> None:
    if sha256_file(DEFAULT_CALIBRATION) != CALIBRATION_SHA:
        raise RuntimeError("CALIBRATION_DATASET_MUTATED")
    if sha256_file(DEFAULT_BOUNDARY) != BOUNDARY_SHA:
        raise RuntimeError("BOUNDARY_DATASET_MUTATED")
    if sha256_file(DEFAULT_FROZEN) != FROZEN_GOLD_SHA:
        raise RuntimeError("FROZEN_GOLD_MUTATED")
    if expected_hashes is not None:
        actual = {path: sha256_file(Path(path)) for path in expected_hashes}
        if actual != expected_hashes:
            raise RuntimeError("BENCHMARK_INPUT_MUTATED")


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gate"]["benchmarkHarnessGate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
