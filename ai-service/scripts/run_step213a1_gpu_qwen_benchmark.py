from __future__ import annotations

"""Run the isolated Step 21.3A.1 local Qwen GPU benchmark."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path, PureWindowsPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.config import ProviderConfig
from app.llm.local_qwen import LocalQwenRuntime, LocalQwenTransformersProvider
from scripts import run_step213a_lite as base


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213a1_gpu"
DEFAULT_REPORT = REPO_ROOT / "docs" / "LOCAL_QWEN_GPU_BENCHMARK_REPORT.md"
PROMPT_PATH = ROOT / "artifacts" / "step213a_lite" / "local_qwen_router_prompt_v1.md"
CPU_OUTPUT_PATH = ROOT / "artifacts" / "step213a_lite" / "local_qwen_router_outputs_v1.jsonl"
CPU_SNAPSHOT_PATH = ROOT / "artifacts" / "step213a_lite" / "local_qwen_model_snapshot_v1.json"
GPU_ENV = ROOT / ".venv-qwen-gpu"
CPU_ENV = ROOT / ".venv"

BENCHMARK_VERSION = "step21.3a.1-local-qwen-gpu-v1"
EXPECTED_PROMPT_HASH = "101D8FAA73E3245720D237AF98031EEDC9EAC054D3E3339C559864DC5EA2CE79"
MIN_CHECKPOINT_SCHEMA = 0.90
MIN_CHECKPOINT_MICRO_F1 = 0.60
MIN_CLEAR_MICRO_F1_GAIN = 0.05
CPU_P50_MS = 51164.0
CPU_P95_MS = 105118.0

PROBE_CASE_IDS = (
    "cal-asap_chinese_reviews-3df4f925a62bca",
    "cal-asap_chinese_reviews-37a649b815d7ae",
    "boundary-e_review_expert_designed-0c5ee871e7a4f8",
    "boundary-figshare_chinese_negative_reviews-023a144527caeb",
    "boundary-v2-e_review_candidate-0216a8a0814d9c",
)

# First 20 cases under a frozen case-id hash ordering. Selection uses metadata only.
CHECKPOINT_CASE_IDS = (
    "boundary-e_review_expert_designed-bc44a5c834863a",
    "cal-asap_chinese_reviews-c069c53811124e",
    "boundary-e_review_expert_designed-e020750b30884b",
    "boundary-v2-e_review_candidate-0e53c02fa5f5f5",
    "boundary-v2-e_review_candidate-22724b6deb63a4",
    "cal-v2-moved-5dca055855af77",
    "boundary-e_review_expert_designed-f500065d5115ea",
    "cal-asap_chinese_reviews-41164411f051e6",
    "boundary-figshare_chinese_negative_reviews-6b71a869facee4",
    "boundary-e_review_expert_designed-1ebfb2e5f98d9e",
    "boundary-e_review_expert_designed-38df96d7c55bdf",
    "boundary-e_review_expert_designed-aebe75f0938851",
    "cal-e_review_expert_designed-896ba5ea510145",
    "boundary-v2-e_review_candidate-0216a8a0814d9c",
    "cal-asap_chinese_reviews-dd9aeb02300988",
    "boundary-v2-e_review_candidate-cf2da54eb0ee5b",
    "boundary-v2-e_review_candidate-2c898c97d01a9b",
    "boundary-v2-e_review_candidate-7438d6bd74c2b3",
    "cal-e_review_expert_designed-2cc8c355bfd9a1",
    "boundary-v2-e_review_candidate-94d61226b769c4",
)

SERVICE_URLS = {
    "8008": "http://127.0.0.1:8008/docs",
    "8083": "http://127.0.0.1:8083/admin/auth/401",
    "9527": "http://127.0.0.1:9527/",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--phase", choices=("auto", "probe", "checkpoint", "full"), default="auto")
    return parser.parse_args()


def configure_offline_gpu_provider(model_dir: Path) -> LocalQwenTransformersProvider:
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "AGENT_LLM_MODEL_PATH": str(model_dir),
            "AGENT_LLM_MODEL_ID": base.MODEL_NAME,
            "AGENT_LLM_DEVICE": "cuda",
            "AGENT_LLM_DTYPE": "bfloat16",
            "AGENT_LLM_MAX_OUTPUT_TOKENS": str(base.GENERATION_CONFIG["maxNewTokens"]),
            "AGENT_LLM_MAX_INPUT_TOKENS": str(base.GENERATION_CONFIG["maxInputTokens"]),
            "AGENT_LLM_ENABLE_THINKING": "false",
        }
    )
    return LocalQwenTransformersProvider(
        ProviderConfig(
            provider_name=base.MODEL_PROVIDER_TYPE,
            base_url="local://transformers",
            model_name=base.MODEL_NAME,
            api_key_env="",
            timeout_seconds=300,
            max_retries=0,
            enabled=True,
        )
    )


def _run_command(arguments: list[str]) -> str:
    result = subprocess.run(arguments, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout.strip()


def _runtime_cpu_environment() -> dict[str, Any]:
    script = (
        "import json,sys,torch,transformers,pydantic;"
        "print(json.dumps({'python':sys.version.split()[0],'torch':torch.__version__,"
        "'cudaAvailable':torch.cuda.is_available(),'transformers':transformers.__version__,"
        "'pydantic':pydantic.__version__}))"
    )
    value = json.loads(_run_command([str(CPU_ENV / "Scripts" / "python.exe"), "-c", script]))
    return {**value, "environmentIdentity": "<repo>/ai-service/.venv"}


def collect_gpu_environment() -> dict[str, Any]:
    import torch
    import transformers

    query = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    ).splitlines()[0]
    name, driver, total, used, free, capability = [item.strip() for item in query.split(",")]
    full = _run_command(["nvidia-smi"])
    cuda_match = re.search(r"CUDA Version:\s*([0-9.]+)", full)
    process_query = _run_command(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ]
    )
    process_names: list[str] = []
    for line in process_query.splitlines():
        parts = [item.strip() for item in line.split(",", 2)]
        if len(parts) >= 2:
            name_part = "unknown" if parts[1].startswith("[") else PureWindowsPath(parts[1]).name
            process_names.append(name_part)
    return {
        "schemaVersion": "gpu-environment-audit-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "gpuEnvironmentGate": "PASS",
        "gpu": {
            "name": name,
            "driverVersion": driver,
            "driverCudaCapability": cuda_match.group(1) if cuda_match else None,
            "computeCapability": capability,
            "totalVramMiB": int(total),
            "usedVramMiB": int(used),
            "freeVramMiB": int(free),
            "processCount": len(process_names),
            "processNames": sorted(set(process_names)),
        },
        "gpuPython": {
            "environmentIdentity": "<repo>/ai-service/.venv-qwen-gpu",
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "torchCudaRuntime": torch.version.cuda,
            "cudaAvailable": torch.cuda.is_available(),
            "deviceCount": torch.cuda.device_count(),
            "deviceName": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "bf16Supported": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
            "transformers": transformers.__version__,
            "officialWheelIndex": "download.pytorch.org/whl/cu126",
        },
        "runtimeCpuEnvironment": _runtime_cpu_environment(),
        "isolated": GPU_ENV.resolve() != CPU_ENV.resolve(),
    }


def check_services() -> dict[str, Any]:
    status: dict[str, Any] = {}
    for port, url in SERVICE_URLS.items():
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                code = int(response.status)
            status[port] = {"httpStatus": code, "available": code == 200}
        except Exception as exc:
            status[port] = {"httpStatus": None, "available": False, "errorType": type(exc).__name__}
    return status


def load_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    split = json.loads(base.DEFAULT_SPLIT.read_text(encoding="utf-8"))
    validation_ids = {row["caseId"] for row in split["rows"] if row["partition"] == "VALIDATION"}
    validation = [
        dict(row, _partition="VALIDATION")
        for row in base.load_jsonl(base.DEFAULT_CALIBRATION)
        if row["caseId"] in validation_ids
    ]
    boundary = [dict(row, _partition="BOUNDARY_CHALLENGE") for row in base.load_jsonl(base.DEFAULT_BOUNDARY)]
    rule_rows = [
        row
        for row in base.load_jsonl(base.DEFAULT_RULE_RESULTS)
        if row["partition"] in {"VALIDATION", "BOUNDARY_CHALLENGE"}
    ]
    if (len(validation), len(boundary), len(rule_rows)) != (40, 60, 100):
        raise RuntimeError("BENCHMARK_CASE_COUNT_MISMATCH")
    return validation, boundary, validation + boundary, {row["caseId"]: row for row in rule_rows}


def select_checkpoint_cases(all_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["caseId"]: row for row in all_cases}
    missing = [case_id for case_id in CHECKPOINT_CASE_IDS if case_id not in by_id]
    if missing:
        raise RuntimeError(f"CHECKPOINT_CASE_MISSING:{','.join(missing)}")
    selected = [by_id[case_id] for case_id in CHECKPOINT_CASE_IDS]
    expected = [row["caseId"] for row in sorted(all_cases, key=lambda row: base.stable_hash(row["caseId"]))[:20]]
    if expected != list(CHECKPOINT_CASE_IDS):
        raise RuntimeError("CHECKPOINT_SELECTION_DRIFT")
    if set(checkpoint_coverage(selected)) != {
        "normal", "explicit", "implicit", "multi-risk", "hard", "hard-negative", "ambiguous", "noisy"
    }:
        raise RuntimeError("CHECKPOINT_COVERAGE_INCOMPLETE")
    return selected


def checkpoint_coverage(rows: list[dict[str, Any]]) -> list[str]:
    coverage: set[str] = set()
    for row in rows:
        expected = base.expected_risks(row)
        if expected == ["normal_review"]:
            coverage.add("normal")
        if row.get("expressionType") in {"explicit", "implicit"}:
            coverage.add(row["expressionType"])
        if row.get("multiRisk"):
            coverage.add("multi-risk")
        if row.get("difficulty") == "hard":
            coverage.add("hard")
        if row.get("boundaryType") == "hard_negative":
            coverage.add("hard-negative")
        if row.get("evaluationTarget") == "ABSTENTION":
            coverage.add("ambiguous")
        if row.get("boundaryType") == "noisy_or_adversarial":
            coverage.add("noisy")
    return sorted(coverage)


def run_case(
    case: dict[str, Any],
    *,
    provider: LocalQwenTransformersProvider,
    prompt_template: str,
    prompt_hash: str,
    model_identity: str,
    rule_by_id: dict[str, dict[str, Any]],
    cache_dir: Path,
    use_cache: bool = True,
    case_id_suffix: str = "",
) -> dict[str, Any]:
    dataset_hash = base.CALIBRATION_SHA if case["_partition"] == "VALIDATION" else base.BOUNDARY_SHA
    inference = base.invoke_local_qwen(
        provider=provider,
        prompt=base.render_prompt(prompt_template, case["textZh"]),
        case_id=case["caseId"] + case_id_suffix,
        dataset_hash=dataset_hash,
        model_identity=model_identity,
        prompt_hash=prompt_hash,
        cache_dir=cache_dir,
        use_cache=use_cache,
    )
    return base.evaluate_output(case, inference, rule_by_id[case["caseId"]])


def probe_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latency = base.latency_metrics(rows)
    p50 = float(latency["p50Ms"])
    latency_gate = "PASS" if p50 <= 5000 else "PASS_WITH_LIMITATIONS" if p50 <= 10000 else "FAIL"
    schema = base.safe_ratio(sum(row["schemaValid"] for row in rows), len(rows))
    return {
        "schemaVersion": "gpu-latency-probe-v1",
        "caseCount": len(rows),
        "caseIds": [row["caseId"] for row in rows],
        "latency": latency,
        "latencyGate": latency_gate,
        "validJsonRate": schema,
        "schemaComplianceRate": schema,
        "schemaCompliantCount": sum(row["schemaValid"] for row in rows),
        "formatRetryCount": sum(row["schemaRetryCount"] for row in rows),
        "schemaGate": "PASS" if schema >= 0.80 else "FAIL",
        "cpuBaseline": {"p50Ms": CPU_P50_MS, "p95Ms": CPU_P95_MS},
        "speedup": {
            "p50": round(CPU_P50_MS / float(latency["p50Ms"]), 4),
            "p95": round(CPU_P95_MS / float(latency["p95Ms"]), 4),
        },
    }


def checkpoint_metrics(
    rows: list[dict[str, Any]],
    rule_rows: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    qwen_quality = base.quality_metrics(rows, completed=False, stop_reason="20_CASE_CHECKPOINT")
    qwen_safety = base.safety_metrics(rows, official=False)
    rule = base.rule_baseline(rule_rows)
    qwen_material_rate = base.safe_ratio(qwen_safety["materialSafetyErrorCount"], len(rows))
    rule_material_rate = base.safe_ratio(rule["materialSafetyErrorCount"], len(rule_rows))
    f1_gain = round(qwen_quality["microF1"] - rule["microF1"], 6)
    conditions = {
        "schemaAtLeast90Percent": qwen_quality["schemaCompliance"] >= MIN_CHECKPOINT_SCHEMA,
        "microF1AtLeast60Percent": qwen_quality["microF1"] >= MIN_CHECKPOINT_MICRO_F1,
        "microF1ClearlyHigherThanRule": f1_gain >= MIN_CLEAR_MICRO_F1_GAIN,
        "materialSafetyErrorRateNotHigherThanRule": qwen_material_rate <= rule_material_rate,
    }
    return {
        "schemaVersion": "gpu-20case-checkpoint-metrics-v1",
        "sampleMethod": "first-20-by-stable-case-id-hash",
        "caseIds": list(CHECKPOINT_CASE_IDS),
        "coverage": checkpoint_coverage(selected),
        "rule": rule,
        "qwen": {**qwen_quality, "materialSafetyErrorCount": qwen_safety["materialSafetyErrorCount"], "materialSafetyErrorRate": qwen_material_rate},
        "microF1Gain": f1_gain,
        "ruleMaterialSafetyErrorRate": rule_material_rate,
        "thresholds": {
            "minimumSchemaCompliance": MIN_CHECKPOINT_SCHEMA,
            "minimumMicroF1": MIN_CHECKPOINT_MICRO_F1,
            "minimumClearMicroF1Gain": MIN_CLEAR_MICRO_F1_GAIN,
        },
        "conditions": conditions,
        "gate": "PASS" if all(conditions.values()) else "FAIL",
    }


def stability_metrics(
    all_cases: list[dict[str, Any]],
    originals: dict[str, dict[str, Any]],
    **run_kwargs: Any,
) -> dict[str, Any]:
    cases = sorted(all_cases, key=lambda row: base.stable_hash(row["caseId"]))[:10]
    risk_stable = decision_stable = 0
    for case in cases:
        repeated = run_case(case, use_cache=False, case_id_suffix="-gpu-stability-repeat", **run_kwargs)
        original = originals[case["caseId"]].get("output") or {}
        output = repeated.get("output") or {}
        risk_stable += set(original.get("riskTypes") or []) == set(output.get("riskTypes") or [])
        decision_stable += original.get("decision") == output.get("decision")
    return {
        "caseCount": len(cases),
        "caseIds": [row["caseId"] for row in cases],
        "riskTypeStability": base.safe_ratio(risk_stable, len(cases)),
        "decisionStability": base.safe_ratio(decision_stable, len(cases)),
    }


def full_gate(quality: dict[str, Any], safety: dict[str, Any], rule: dict[str, Any]) -> str:
    strict = (
        quality["microF1"] >= 0.80
        and quality["boundary"]["overall"]["microF1"] >= 0.75
        and quality["slices"]["multiRisk"]["microF1"] >= 0.75
        and safety["materialSafetyErrorCount"] < rule["materialSafetyErrorCount"]
    )
    limited = (
        quality["microF1"] >= 0.75
        and quality["microF1"] - rule["microF1"] >= 0.20
        and safety["materialSafetyErrorCount"] < rule["materialSafetyErrorCount"]
    )
    return "PASS" if strict else "PASS_WITH_LIMITATIONS" if limited else "FAIL"


def build_report(
    environment: dict[str, Any],
    snapshot: dict[str, Any],
    probe: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    quality: dict[str, Any] | None,
    safety: dict[str, Any] | None,
    reliability: dict[str, Any] | None,
    services_before: dict[str, Any],
    services_after: dict[str, Any],
    gate: dict[str, Any],
) -> str:
    gpu = environment["gpu"]
    lines = [
        "# Local Qwen GPU Benchmark Report",
        "",
        "## Scope",
        "",
        "Step 21.3A.1 measures the existing local Qwen3-1.7B model in an isolated CUDA environment. Runtime routing, Safety Gate, datasets, Frozen Gold, and production model loading are unchanged.",
        "",
        "## GPU Environment",
        "",
        f"- GPU: `{gpu['name']}`; VRAM `{gpu['totalVramMiB']} MiB` total / `{gpu['freeVramMiB']} MiB` free at audit.",
        f"- Driver: `{gpu['driverVersion']}`; driver CUDA capability `{gpu['driverCudaCapability']}`.",
        f"- PyTorch: `{environment['gpuPython']['torch']}`; CUDA runtime `{environment['gpuPython']['torchCudaRuntime']}`.",
        f"- Actual model device / dtype: `{snapshot['device']}` / `{snapshot['dtype']}`.",
        f"- Peak allocated / reserved VRAM: `{snapshot['memory']['peakAllocatedVramMiB']}` / `{snapshot['memory']['peakReservedVramMiB']}` MiB.",
        "",
        "## Five Case Probe",
        "",
        f"GPU P50 `{probe['latency']['p50Ms']} ms`, P95 `{probe['latency']['p95Ms']} ms`, P99 `{probe['latency']['p99Ms']} ms`.",
        f"CPU-to-GPU speedup: P50 `{probe['speedup']['p50']}x`, P95 `{probe['speedup']['p95']}x`.",
        f"Schema compliance `{probe['schemaComplianceRate']:.4f}`; retries `{probe['formatRetryCount']}`.",
        "",
        "## 20 Case Checkpoint",
        "",
    ]
    if checkpoint:
        lines.extend(
            [
                f"Gate: `{checkpoint['gate']}`; coverage: `{', '.join(checkpoint['coverage'])}`.",
                "",
                "| Metric | Rule | Qwen GPU |",
                "| --- | ---: | ---: |",
                f"| Exact Accuracy | {checkpoint['rule']['exactSetMatchAccuracy']:.4f} | {checkpoint['qwen']['exactSetMatchAccuracy']:.4f} |",
                f"| Micro F1 | {checkpoint['rule']['microF1']:.4f} | {checkpoint['qwen']['microF1']:.4f} |",
                f"| Material Safety Errors | {checkpoint['rule']['materialSafetyErrorCount']} | {checkpoint['qwen']['materialSafetyErrorCount']} |",
            ]
        )
    else:
        lines.append("Not run.")
    lines.extend(["", "## Full Benchmark", ""])
    if quality and safety and reliability:
        lines.extend(
            [
                f"100-case benchmark completed. Exact `{quality['exactSetMatchAccuracy']:.4f}`, Micro F1 `{quality['microF1']:.4f}`, Macro F1 `{quality['macroF1']:.4f}`.",
                f"Boundary F1 `{quality['boundary']['overall']['microF1']:.4f}`, Multi-risk F1 `{quality['slices']['multiRisk']['microF1']:.4f}`, Abstention accuracy `{quality['abstention']['accuracy']:.4f}`.",
                f"Material safety errors `{safety['materialSafetyErrorCount']}`. Fast-path candidate `{reliability['fastPathCandidateGate']}`.",
            ]
        )
    else:
        lines.append("Not run because the staged checkpoint did not authorize it.")
    lines.extend(
        [
            "",
            "## Integrity",
            "",
            f"- Prompt hash: `{snapshot['promptHash']}` (identical to CPU probe).",
            f"- Generation config hash: `{snapshot['generationConfigHash']}` (identical to CPU probe).",
            f"- Frozen Gold not executed; SHA `{base.FROZEN_GOLD_SHA}`.",
            "- External model/API calls: `0`.",
            f"- Runtime services before: `{json.dumps(services_before, sort_keys=True)}`.",
            f"- Runtime services after: `{json.dumps(services_after, sort_keys=True)}`.",
            "",
            "## Gates",
            "",
            *(f"- `{key}` = `{value}`" for key, value in gate.items() if key.endswith("Gate")),
            "",
            "## Recommendation",
            "",
            f"`{gate['nextRecommendation']}`",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    import torch

    protected = [base.DEFAULT_CALIBRATION, base.DEFAULT_BOUNDARY, base.DEFAULT_FROZEN, base.DEFAULT_SPLIT, base.DEFAULT_RULE_RESULTS]
    before_hashes = {str(path): base.sha256_file(path) for path in protected}
    base.assert_protected_unchanged(before_hashes)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    prompt_hash = hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest().upper()
    if prompt_hash != EXPECTED_PROMPT_HASH:
        raise RuntimeError("CPU_PROMPT_HASH_MISMATCH")
    cpu_probe_ids = tuple(row["caseId"] for row in base.load_jsonl(CPU_OUTPUT_PATH))
    if cpu_probe_ids != PROBE_CASE_IDS:
        raise RuntimeError("CPU_PROBE_CASE_IDS_MISMATCH")

    services_before = check_services()
    environment = collect_gpu_environment()
    base.write_json(args.output_dir / "gpu_environment_audit_v1.json", environment)
    if not environment["gpuPython"]["cudaAvailable"] or environment["gpuPython"]["deviceCount"] < 1:
        raise RuntimeError("GPU_PYTORCH_NOT_AVAILABLE")

    model_dir = base.discover_local_model(args.model_dir)
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    validation, boundary, all_cases, rule_by_id = load_cases()
    checkpoint_cases = select_checkpoint_cases(all_cases)
    probe_cases = base.select_probe_cases(validation, boundary)
    if tuple(row["caseId"] for row in probe_cases) != PROBE_CASE_IDS:
        raise RuntimeError("GPU_PROBE_SELECTION_DRIFT")

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    provider = configure_offline_gpu_provider(model_dir)
    smoke = base.invoke_local_qwen(
        provider=provider,
        prompt=base.render_prompt(prompt_template, "商品与描述一致，使用正常。"),
        case_id="step213a1-gpu-availability-smoke",
        dataset_hash="GPU_AVAILABILITY_SMOKE_V1",
        model_identity=base.model_snapshot(model_dir)["modelFingerprint"],
        prompt_hash=prompt_hash,
        cache_dir=args.output_dir / "cache",
        use_cache=False,
    )
    runtime = LocalQwenRuntime.status()
    if not runtime["loaded"] or not str(runtime["device"]).startswith("cuda"):
        raise RuntimeError("QWEN_MODEL_NOT_ON_CUDA")
    snapshot = {
        **base.model_snapshot(model_dir),
        "schemaVersion": "local-qwen-gpu-model-snapshot-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "device": runtime["device"],
        "dtype": runtime["dtype"],
        "quantized": False,
        "cpuOffload": False,
        "batchSize": 1,
        "promptHash": prompt_hash,
        "generationConfigHash": base.generation_config_hash(),
        "availability": {
            "inferenceSucceeded": smoke["errorCode"] in {None, "LOCAL_QWEN_SCHEMA_INVALID"},
            "schemaValid": smoke["schemaValid"],
            "latencyMs": smoke["latencyMs"],
        },
        "memory": {
            "allocatedVramMiB": round(torch.cuda.memory_allocated() / 1048576, 2),
            "reservedVramMiB": round(torch.cuda.memory_reserved() / 1048576, 2),
            "peakAllocatedVramMiB": round(torch.cuda.max_memory_allocated() / 1048576, 2),
            "peakReservedVramMiB": round(torch.cuda.max_memory_reserved() / 1048576, 2),
        },
        "externalApiCallCount": 0,
    }
    base.write_json(args.output_dir / "local_qwen_gpu_model_snapshot_v1.json", snapshot)

    common = {
        "provider": provider,
        "prompt_template": prompt_template,
        "prompt_hash": prompt_hash,
        "model_identity": snapshot["modelFingerprint"],
        "rule_by_id": rule_by_id,
        "cache_dir": args.output_dir / "cache",
    }
    probe_rows: list[dict[str, Any]] = []
    for case in probe_cases:
        tagged = dict(case, probeType=case.get("probeType"))
        probe_rows.append(run_case(tagged, **common))
    probe = probe_metrics(probe_rows)
    probe["rows"] = probe_rows
    base.write_json(args.output_dir / "gpu_latency_probe_v1.json", probe)

    checkpoint: dict[str, Any] | None = None
    quality = safety = reliability = comparison = None
    full_benchmark_gate = "NOT_RUN_CHECKPOINT_REQUIRED"
    if args.phase != "probe":
        checkpoint_rows: list[dict[str, Any]] = []
        for case in checkpoint_cases:
            checkpoint_rows.append(run_case(case, **common))
            base.write_jsonl(args.output_dir / "gpu_20case_checkpoint_outputs_v1.jsonl", checkpoint_rows)
        checkpoint_rule_rows = [rule_by_id[case_id] for case_id in CHECKPOINT_CASE_IDS]
        checkpoint = checkpoint_metrics(checkpoint_rows, checkpoint_rule_rows, checkpoint_cases)
        base.write_json(args.output_dir / "gpu_20case_checkpoint_metrics_v1.json", checkpoint)

        should_run_full = checkpoint["gate"] == "PASS" and args.phase in {"auto", "full"}
        if should_run_full:
            rows_by_id = {row["caseId"]: row for row in checkpoint_rows}
            ordered_rows: list[dict[str, Any]] = []
            for case in all_cases:
                row = rows_by_id.get(case["caseId"])
                if row is None:
                    row = run_case(case, **common)
                    rows_by_id[case["caseId"]] = row
                ordered_rows.append(row)
                base.write_jsonl(args.output_dir / "local_qwen_gpu_router_outputs_v1.jsonl", ordered_rows)
            quality = base.quality_metrics(ordered_rows, completed=True)
            safety = base.safety_metrics(ordered_rows, official=True)
            reliability = base.reliability_metrics(ordered_rows, official=True)
            reliability["stability"] = stability_metrics(all_cases, rows_by_id, **common)
            rule_full = base.rule_baseline([rule_by_id[row["caseId"]] for row in all_cases])
            comparison = base.comparison_artifact(rule_full, quality, completed=True)
            comparison["localQwen"]["materialSafetyErrorCount"] = safety["materialSafetyErrorCount"]
            comparison["localQwen"]["latency"] = base.latency_metrics(ordered_rows)
            comparison["cpuProbeLatency"] = {"p50Ms": CPU_P50_MS, "p95Ms": CPU_P95_MS}
            comparison["gpuProbeLatency"] = probe["latency"]
            comparison["speedup"] = probe["speedup"]
            comparison["improvements"]["materialSafetyErrorReduction"] = (
                rule_full["materialSafetyErrorCount"] - safety["materialSafetyErrorCount"]
            )
            full_benchmark_gate = full_gate(quality, safety, rule_full)
            base.write_json(args.output_dir / "local_qwen_gpu_quality_metrics_v1.json", quality)
            base.write_json(args.output_dir / "local_qwen_gpu_safety_metrics_v1.json", safety)
            base.write_json(args.output_dir / "local_qwen_gpu_reliability_metrics_v1.json", reliability)
            base.write_json(args.output_dir / "rule_vs_qwen_gpu_comparison_v1.json", comparison)
        elif checkpoint["gate"] != "PASS":
            full_benchmark_gate = "NOT_RUN_CHECKPOINT_FAILED"
        elif args.phase == "checkpoint":
            full_benchmark_gate = "NOT_RUN_CHECKPOINT_ONLY"

    snapshot["memory"].update(
        {
            "allocatedVramMiB": round(torch.cuda.memory_allocated() / 1048576, 2),
            "reservedVramMiB": round(torch.cuda.memory_reserved() / 1048576, 2),
            "peakAllocatedVramMiB": round(torch.cuda.max_memory_allocated() / 1048576, 2),
            "peakReservedVramMiB": round(torch.cuda.max_memory_reserved() / 1048576, 2),
        }
    )
    max_input_tokens = max((row.get("inputTokens") or 0 for row in probe_rows), default=0)
    if checkpoint:
        max_input_tokens = max(max_input_tokens, max((row.get("inputTokens") or 0 for row in base.load_jsonl(args.output_dir / "gpu_20case_checkpoint_outputs_v1.jsonl")), default=0))
    snapshot["observedMaxInputTokens"] = max_input_tokens
    snapshot["contextAllocationBounded"] = max_input_tokens < base.GENERATION_CONFIG["maxInputTokens"] < snapshot["contextLength"]
    base.write_json(args.output_dir / "local_qwen_gpu_model_snapshot_v1.json", snapshot)

    services_after = check_services()
    services_gate = "PASS" if all(item["available"] for item in services_before.values()) and all(item["available"] for item in services_after.values()) else "FAIL"
    checkpoint_gate = checkpoint["gate"] if checkpoint else "NOT_RUN"
    if probe["latencyGate"] == "FAIL":
        final_gate = "FAIL_LOCAL_QWEN_LATENCY"
        recommendation = "LOCAL_GPU_INFERENCE_TOO_SLOW"
    elif checkpoint and checkpoint_gate == "FAIL":
        final_gate = "FAIL_LOCAL_QWEN_QUALITY"
        recommendation = "QWEN_1_7B_CAPACITY_INSUFFICIENT"
    elif quality and full_benchmark_gate == "FAIL":
        final_gate = "FAIL_LOCAL_QWEN_QUALITY"
        recommendation = "QWEN_1_7B_CAPACITY_INSUFFICIENT"
    elif quality:
        final_gate = "PASS_WITH_LIMITATIONS" if "PASS_WITH_LIMITATIONS" in {probe["latencyGate"], full_benchmark_gate} else "PASS"
        recommendation = "LOCAL_QWEN_ROUTER_CANDIDATE"
    else:
        final_gate = "PASS_WITH_LIMITATIONS"
        recommendation = "CHECKPOINT_ONLY_NO_RUNTIME_DECISION"
    gate = {
        "gpuEnvironmentGate": environment["gpuEnvironmentGate"],
        "gpuPytorchGate": "PASS",
        "gpuModelLoadGate": "PASS",
        "gpuLatencyGate": probe["latencyGate"],
        "gpuSchemaGate": probe["schemaGate"],
        "localQwen20CaseQualityGate": checkpoint_gate,
        "localQwen100CaseBenchmarkGate": full_benchmark_gate,
        "runtimeServicesGate": services_gate,
        "step21_3a_1Gate": final_gate,
        "fullBenchmarkCompleted": quality is not None,
        "frozenBenchmarkExecuted": False,
        "frozenGoldSha": base.FROZEN_GOLD_SHA,
        "externalApiCallCount": 0,
        "nextRecommendation": recommendation,
    }
    base.write_json(args.output_dir / "step213a1_gpu_gate_v1.json", gate)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        build_report(environment, snapshot, probe, checkpoint, quality, safety, reliability, services_before, services_after, gate),
        encoding="utf-8",
        newline="\n",
    )
    base.assert_protected_unchanged(before_hashes)
    return {
        "environment": environment,
        "snapshot": snapshot,
        "probe": probe,
        "checkpoint": checkpoint,
        "quality": quality,
        "safety": safety,
        "reliability": reliability,
        "comparison": comparison,
        "servicesBefore": services_before,
        "servicesAfter": services_after,
        "gate": gate,
    }


def main() -> int:
    result = run(parse_args())
    print(json.dumps({"gate": result["gate"], "probe": result["probe"], "checkpoint": result["checkpoint"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
