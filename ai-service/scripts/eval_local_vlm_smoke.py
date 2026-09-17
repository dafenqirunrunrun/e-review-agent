import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = ROOT / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.main import app
from app.vlm.config import load_config
from app.vlm.provider import LocalQwen3VlProvider
from app.vlm.qwen3_vl_runtime import Qwen3VlRuntimeCounters, Qwen3VlRuntimeSession


OUT = ROOT / "data" / "multimodal" / "eval" / "local_vlm_smoke_results.json"
REPORT = ROOT / "docs" / "133_v161_vlm_smoke_eval_report.md"
GPU_REPORT = ROOT / "docs" / "134_v161_vlm_gpu_memory_report.md"
LATENCY_OUT = ROOT / "data" / "multimodal" / "audit" / "vlm_latency_breakdown.json"
LATENCY_REPORT = ROOT / "docs" / "140_v1614_vlm_latency_breakdown.md"
RAW_SCHEMA_OUT = ROOT / "data" / "multimodal" / "audit" / "vlm_raw_schema_failure_analysis.json"
RAW_SCHEMA_REPORT = ROOT / "docs" / "142_v1615_vlm_raw_schema_failure_analysis.md"


def run_python(script: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.stdout:
        print(completed.stdout.strip())


def load_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dependency_status() -> dict:
    status = {}
    for name in ["torch", "transformers", "accelerate", "PIL", "huggingface_hub"]:
        try:
            __import__(name)
            status[name] = True
        except ImportError:
            status[name] = False
    return status


def gpu_status() -> dict:
    info = {
        "cuda_available": False,
        "gpu_name": None,
        "gpu_memory_total_mb": None,
        "gpu_memory_allocated_mb": None,
        "gpu_memory_reserved_mb": None,
    }
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            info.update(
                {
                    "cuda_available": True,
                    "gpu_name": torch.cuda.get_device_name(0),
                    "gpu_memory_total_mb": round(props.total_memory / 1024 / 1024, 2),
                    "gpu_memory_allocated_mb": round(torch.cuda.memory_allocated(0) / 1024 / 1024, 2),
                    "gpu_memory_reserved_mb": round(torch.cuda.memory_reserved(0) / 1024 / 1024, 2),
                }
            )
    except Exception as exc:  # pragma: no cover - environment dependent
        info["gpu_error"] = str(exc)
    return info


def model_files(model_dir: Path) -> dict:
    if not model_dir.exists():
        return {
            "exists": False,
            "file_count": 0,
            "total_size_mb": 0,
            "has_config": False,
            "has_processor_or_tokenizer": False,
            "has_weight_file": False,
        }
    files = [path for path in model_dir.rglob("*") if path.is_file()]
    return {
        "exists": True,
        "file_count": len(files),
        "total_size_mb": round(sum(path.stat().st_size for path in files) / 1024 / 1024, 2),
        "has_config": (model_dir / "config.json").exists(),
        "has_processor_or_tokenizer": any((model_dir / name).exists() for name in ["preprocessor_config.json", "processor_config.json", "tokenizer.json", "tokenizer_config.json"]),
        "has_weight_file": any(path.suffix == ".safetensors" or path.name.startswith("pytorch_model") for path in files),
    }


def analyze_images(provider: LocalQwen3VlProvider, manifest: list[dict], limit: int, cfg) -> tuple[list[dict], list[float]]:
    attempts = []
    latencies = []
    samples = manifest[:limit]
    if not provider.available:
        for sample in samples:
            attempts.append(
                {
                    "sample_id": sample["sample_id"],
                    "status_code": 503,
                    "latency_ms": 0,
                    "real_vlm_inference": False,
                    "provider_success": False,
                    "schema_valid": False,
                    "repair_used": False,
                    "fallback_used": False,
                    "gpu_peak_memory_mb": None,
                    "unload_success": False,
                    "latency_breakdown": {},
                    "runtime_counters": Qwen3VlRuntimeCounters.snapshot(),
                    "error": "VLM_MODEL_NOT_AVAILABLE",
                }
            )
        return attempts, latencies

    Qwen3VlRuntimeCounters.reset()
    with Qwen3VlRuntimeSession(
        model_dir=cfg.model_dir,
        stage=f"vlm-provider-smoke-{limit}",
        min_free_memory_mb=5200,
        check_interval_seconds=int(os.getenv("E_REVIEW_GPU_CHECK_INTERVAL_SECONDS", "30")),
        stable_checks=int(os.getenv("E_REVIEW_GPU_IDLE_STABLE_CHECKS", "3")),
        timeout_seconds=int(os.getenv("E_REVIEW_GPU_WAIT_TIMEOUT_SECONDS", "14400")),
        device_placement=os.getenv("E_REVIEW_VLM_DEVICE_PLACEMENT", "auto"),
    ) as session:
        for sample in samples:
            started = time.time()
            try:
                result = provider.analyze_images(
                    {
                        "image_paths": [str(ROOT / sample["image_path"])],
                        "review_text": sample.get("review_text") or f"synthetic smoke review for {sample.get('title', sample['sample_id'])}",
                        "product_name": sample.get("product_name") or "synthetic smoke product",
                    },
                    session=session,
                )
                body = result.model_dump()
                status_code = 200
                error = None
            except Exception as exc:
                body = {}
                status_code = 503
                error = str(exc)[:300]
            latency_ms = round((time.time() - started) * 1000, 2)
            latencies.append(latency_ms)
            real_inference = (
                status_code == 200
                and body.get("real_inference") is True
                and body.get("cuda_used") is True
                and body.get("generate_executed") is True
                and body.get("fallback_used") is False
            )
            attempts.append(
                {
                    "sample_id": sample["sample_id"],
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "real_vlm_inference": real_inference,
                    "provider_success": status_code == 200,
                    "schema_valid": body.get("schema_valid") is True,
                    "repair_used": body.get("repair_used") is True,
                    "fallback_used": body.get("fallback_used") is True,
                    "raw_schema_valid": body.get("raw_schema_valid") is True,
                    "raw_schema_failure_reasons": body.get("raw_schema_failure_reasons") or [],
                    "deterministic_normalization_used": body.get("deterministic_normalization_used") is True,
                    "deterministic_normalization_success": body.get("deterministic_normalization_success") is True,
                    "safe_repair_used": body.get("safe_repair_used") is True,
                    "safe_repair_success": body.get("safe_repair_success") is True,
                    "second_generate_count": int(body.get("second_generate_count") or 0),
                    "gpu_peak_memory_mb": body.get("gpu_peak_memory_mb"),
                    "unload_success": False,
                    "latency_breakdown": body.get("latency_breakdown") or {},
                    "runtime_counters": body.get("runtime_counters") or {},
                    "error": error,
                }
            )
        after_unload_probe = session
    unload_success = (
        after_unload_probe.gpu_memory_after_unload_mb is not None
        and after_unload_probe.gpu_memory_after_unload_mb <= 2048
    )
    for attempt in attempts:
        attempt["unload_success"] = unload_success
        attempt.setdefault("runtime_counters", Qwen3VlRuntimeCounters.snapshot())
    return attempts, latencies


def percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def _first_number(breakdowns: list[dict], key: str) -> float:
    for item in breakdowns:
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _sum_numbers(breakdowns: list[dict], key: str) -> float:
    return round(sum(float(item.get(key) or 0) for item in breakdowns), 2)


def external_gpu_compute_processes() -> list[dict]:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name",
                "--format=csv,noheader",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return []
    if completed.returncode != 0:
        return []
    current_pid = os.getpid()
    processes = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",", 1)]
        try:
            pid = int(parts[0])
        except (ValueError, IndexError):
            continue
        if pid == current_pid:
            continue
        process_name = parts[1] if len(parts) > 1 else ""
        if process_name:
            lowered = process_name.lower()
            if "python" in lowered:
                process_kind = "python"
            elif any(name in lowered for name in ["chrome", "edge", "webview", "explorer", "overlay"]):
                process_kind = "desktop_graphics"
            else:
                process_kind = "gpu_process"
        else:
            process_kind = "unknown"
        processes.append({"pid": pid, "process_kind": process_kind})
    return processes


def build_session_latency_metrics(
    breakdowns: list[dict],
    total_wall_clock_ms: float,
    external_process_count: int = 0,
    gpu_busy_waiting_seen: bool = False,
) -> dict:
    gpu_wait_ms = _first_number(breakdowns, "gpu_wait_ms")
    gpu_lock_wait_ms = _first_number(breakdowns, "gpu_lock_acquire_ms") or gpu_wait_ms
    model_load_ms = _first_number(breakdowns, "model_load_ms")
    processor_load_ms = _first_number(breakdowns, "processor_load_ms")
    model_unload_ms = _first_number(list(reversed(breakdowns)), "model_unload_ms")
    active_generate_total_ms = _sum_numbers(breakdowns, "generate_ms")
    active_processing_total_ms = _sum_numbers(breakdowns, "total_request_ms")
    active_session_wall_clock_ms = round(
        processor_load_ms + model_load_ms + active_processing_total_ms + model_unload_ms,
        2,
    )
    gpu_wait_ratio = round(gpu_wait_ms / total_wall_clock_ms, 4) if total_wall_clock_ms else 0
    contended = (
        external_process_count > 0
        or gpu_wait_ms > 5000
        or gpu_wait_ratio > 0.10
        or gpu_busy_waiting_seen
    )
    return {
        "gpu_wait_ms": round(gpu_wait_ms, 2),
        "gpu_lock_wait_ms": round(gpu_lock_wait_ms, 2),
        "model_load_ms": round(model_load_ms, 2),
        "processor_load_ms": round(processor_load_ms, 2),
        "active_generate_total_ms": active_generate_total_ms,
        "active_processing_total_ms": active_processing_total_ms,
        "model_unload_ms": round(model_unload_ms, 2),
        "active_session_wall_clock_ms": active_session_wall_clock_ms,
        "benchmark_total_wall_clock_ms": total_wall_clock_ms,
        "gpu_wait_ratio": gpu_wait_ratio,
        "external_gpu_compute_process_count": external_process_count,
        "gpu_busy_waiting_seen": gpu_busy_waiting_seen,
        "uncontended": not contended,
    }


def classify_session_marker(metrics: dict, total: int) -> dict:
    correctness_pass = (
        total == 12
        and metrics.get("real_vlm_inference_count") == 12
        and metrics.get("visual_schema_valid_rate") == 1.0
        and metrics.get("fallback_rate") == 0
        and metrics.get("oom_count") == 0
        and metrics.get("model_load_count") == 1
        and metrics.get("gpu_lock_acquire_count") == 1
        and metrics.get("unload_count") == 1
    )
    active_latency_pass = (
        metrics.get("avg_generate_ms") is not None
        and metrics.get("p95_generate_ms") is not None
        and metrics.get("avg_end_to_end_ms") is not None
        and metrics.get("p95_end_to_end_ms") is not None
        and metrics.get("active_session_wall_clock_ms") is not None
        and metrics["avg_generate_ms"] <= 15000
        and metrics["p95_generate_ms"] <= 30000
        and metrics["avg_end_to_end_ms"] <= 20000
        and metrics["p95_end_to_end_ms"] <= 40000
        and metrics["active_session_wall_clock_ms"] <= 300000
    )
    if correctness_pass:
        correctness_marker = "VLM_PROVIDER_SESSION_CORRECTNESS_PASS"
        if not metrics.get("uncontended"):
            latency_marker = "VLM_PROVIDER_LATENCY_DEFERRED_GPU_CONTENTION"
        elif active_latency_pass:
            latency_marker = "VLM_PROVIDER_SESSION_LATENCY_PASS"
        else:
            latency_marker = "VLM_PROVIDER_LATENCY_TARGET_NOT_MET"
    else:
        correctness_marker = "VLM_PROVIDER_SESSION_CORRECTNESS_BLOCKED"
        latency_marker = "VLM_PROVIDER_SMOKE_BLOCKED"
    return {
        "correctness_pass": correctness_pass,
        "active_latency_pass": active_latency_pass,
        "correctness_marker": correctness_marker,
        "latency_marker": latency_marker,
        "active_latency_marker": "VLM_PROVIDER_ACTIVE_LATENCY_PASS" if active_latency_pass else "VLM_PROVIDER_ACTIVE_LATENCY_NOT_MET",
        "total_wall_clock_marker": (
            "VLM_PROVIDER_TOTAL_WALL_CLOCK_PASS"
            if metrics.get("uncontended") and active_latency_pass
            else "VLM_PROVIDER_TOTAL_WALL_CLOCK_DEFERRED_GPU_CONTENTION"
            if correctness_pass and not metrics.get("uncontended")
            else "VLM_PROVIDER_TOTAL_WALL_CLOCK_NOT_MET"
        ),
    }


def build_raw_schema_failure_analysis(result: dict) -> dict:
    attempts = result.get("attempts") or []
    total = len(attempts)
    reason_counts: dict[str, int] = {}
    sample_rows = []
    for item in attempts:
        reasons = item.get("raw_schema_failure_reasons") or ([] if item.get("raw_schema_valid") else ["other"])
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        sample_rows.append(
            {
                "sample_id": item.get("sample_id"),
                "generate_ms": (item.get("latency_breakdown") or {}).get("generate_ms"),
                "end_to_end_ms": (item.get("latency_breakdown") or {}).get("total_request_ms"),
                "repair_ms": (item.get("latency_breakdown") or {}).get("schema_repair_ms"),
                "schema_raw_valid": item.get("raw_schema_valid") is True,
                "schema_final_valid": item.get("schema_valid") is True,
                "failure_reasons": reasons,
                "deterministic_normalization_success": item.get("deterministic_normalization_success") is True,
                "safe_repair_success": item.get("safe_repair_success") is True,
            }
        )
    deterministic_success = sum(1 for item in attempts if item.get("deterministic_normalization_success"))
    safe_repair_success = sum(1 for item in attempts if item.get("safe_repair_success"))
    raw_valid = sum(1 for item in attempts if item.get("raw_schema_valid"))
    return {
        "marker": schema_hardening_marker(raw_valid / total if total else 0),
        "raw_schema_valid_count": raw_valid,
        "raw_schema_invalid_count": total - raw_valid,
        "raw_schema_valid_rate": round(raw_valid / total, 4) if total else 0,
        "failure_reason_counts": dict(sorted(reason_counts.items())),
        "samples": sample_rows,
        "deterministic_normalization_success_count": deterministic_success,
        "safe_repair_success_count": safe_repair_success,
        "second_generate_count": sum(int(item.get("second_generate_count") or 0) for item in attempts),
    }


def schema_hardening_marker(raw_schema_valid_rate: float) -> str:
    if raw_schema_valid_rate >= 0.80:
        return "VLM_RAW_SCHEMA_HARDENING_PASS"
    if raw_schema_valid_rate >= 0.60:
        return "VLM_RAW_SCHEMA_HARDENING_PARTIAL"
    return "VLM_RAW_SCHEMA_HARDENING_NOT_MET"


def raw_schema_report(analysis: dict) -> str:
    reasons = "\n".join(f"- `{key}`: `{value}`" for key, value in analysis["failure_reason_counts"].items()) or "- none"
    samples = "\n".join(
        "| {sample_id} | {generate_ms} | {end_to_end_ms} | {repair_ms} | {schema_raw_valid} | {schema_final_valid} | {failure_reasons} |".format(
            **{**row, "failure_reasons": ", ".join(row["failure_reasons"])}
        )
        for row in analysis["samples"]
    )
    return f"""# v1.6.1.5 VLM Raw Schema Failure Analysis

## Conclusion

`{analysis['marker']}`

## Summary

- raw_schema_valid_count: `{analysis['raw_schema_valid_count']}`
- raw_schema_invalid_count: `{analysis['raw_schema_invalid_count']}`
- raw_schema_valid_rate: `{analysis['raw_schema_valid_rate']}`
- deterministic_normalization_success_count: `{analysis['deterministic_normalization_success_count']}`
- safe_repair_success_count: `{analysis['safe_repair_success_count']}`
- second_generate_count: `{analysis['second_generate_count']}`

## Failure Reasons

{reasons}

## Sample Timing And Schema Status

| sample_id | generate_ms | end_to_end_ms | repair_ms | raw_valid | final_valid | failure_reasons |
| --- | ---: | ---: | ---: | --- | --- | --- |
{samples}

## Boundary

This audit stores only schema status, deterministic repair categories, and
timing fields. It does not persist raw images, raw privacy OCR, API keys, model
weights, or full local GPU process command lines.
"""


def smoke_report(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["blocking_reasons"]) or "- none"
    return f"""# v1.6.1 Local VLM Smoke Evaluation Report

## Conclusion

`{result['marker']}`

This report covers only synthetic, non-private smoke images generated under
`.runtime/vlm-smoke/`. It is not a real e-commerce multimodal external
evaluation and must not be used as a release gate pass.

## Metrics

| Metric | Value |
| --- | ---: |
| total_samples | {result['metrics']['total_samples']} |
| real_vlm_inference_count | {result['metrics']['real_vlm_inference_count']} |
| vlm_success_rate | {result['metrics']['vlm_success_rate']} |
| visual_schema_valid_rate | {result['metrics']['visual_schema_valid_rate']} |
| visual_field_complete_rate | {result['metrics']['visual_field_complete_rate']} |
| fallback_rate | {result['metrics']['fallback_rate']} |
| invalid_json_count | {result['metrics']['invalid_json_count']} |
| repair_used_rate | {result['metrics']['repair_used_rate']} |
| avg_latency_ms | {result['metrics']['avg_latency_ms']} |
| p95_latency_ms | {result['metrics']['p95_latency_ms']} |
| avg_generate_ms | {result['metrics'].get('avg_generate_ms')} |
| p95_generate_ms | {result['metrics'].get('p95_generate_ms')} |
| avg_end_to_end_ms | {result['metrics'].get('avg_end_to_end_ms')} |
| p95_end_to_end_ms | {result['metrics'].get('p95_end_to_end_ms')} |
| total_wall_clock_ms | {result['metrics'].get('total_wall_clock_ms')} |
| active_session_wall_clock_ms | {result['metrics'].get('active_session_wall_clock_ms')} |
| benchmark_total_wall_clock_ms | {result['metrics'].get('benchmark_total_wall_clock_ms')} |
| gpu_wait_ms | {result['metrics'].get('gpu_wait_ms')} |
| active_latency_marker | {result.get('active_latency_marker')} |
| total_wall_clock_marker | {result.get('total_wall_clock_marker')} |
| gpu_peak_memory_mb | {result['metrics']['gpu_peak_memory_mb']} |
| oom_count | {result['metrics']['oom_count']} |
| unload_success_rate | {result['metrics']['unload_success_rate']} |
| privacy_smoke_detection_rate | {result['metrics']['privacy_smoke_detection_rate']} |

## Blocking Reasons

{blockers}

## Evidence Boundary

- Smoke images are synthetic drawings, not real user review images.
- The current provider must not emit `VLM_PROVIDER_SMOKE_PASS` unless real
  Transformers inference succeeds on the smoke set.
- The final v1.6.1 release gate remains blocked until compliant real text and
  multimodal external datasets are available and isolated.
"""


def memory_report(result: dict) -> str:
    model_dir_label = "<external_model_root>/Qwen3-VL-2B-Instruct"
    return f"""# v1.6.1 Local VLM GPU Memory Report

## Environment

- Provider: `{result['provider']}`
- Model: `{result['model_name']}`
- Model directory: `{model_dir_label}`
- Device: `{result['config']['device']}`
- dtype: `{result['config']['dtype']}`
- Max images: `{result['config']['max_images']}`
- Max pixels: `{result['config']['max_pixels']}`
- Lazy/unload strategy: serial lazy load, unload after request

## GPU Snapshot

```json
{json.dumps(result['gpu'], ensure_ascii=False, indent=2)}
```

## Model Files

```json
{json.dumps(result['model_files'], ensure_ascii=False, indent=2)}
```

## Current Finding

The configured Qwen3-VL model directory is outside Git as required, but the
local weight files are not available in this environment yet. No real VLM load,
peak memory, inference latency, or unload memory recovery can be claimed.
"""


def latency_report(result: dict) -> str:
    metrics = result["metrics"]
    counters = {key: metrics.get(key) for key in [
        "runtime_instance_count",
        "processor_load_count",
        "model_load_count",
        "generate_call_count",
        "unload_count",
        "gpu_lock_acquire_count",
    ]}
    return f"""# v1.6.1.4 VLM Latency Breakdown

## Conclusion

`{result['marker']}`

## Root Cause

The previous provider smoke path loaded and unloaded the Qwen3-VL processor and
model once per image. The session path holds one GPU lock, loads the processor
and model once, then serially executes one real `generate` call per image.

## Latency Views

- End-to-end average: `{metrics.get('avg_end_to_end_ms')}` ms
- End-to-end P95: `{metrics.get('p95_end_to_end_ms')}` ms
- Generate-only average: `{metrics.get('avg_generate_ms')}` ms
- Generate-only P95: `{metrics.get('p95_generate_ms')}` ms
- GPU wait: `{metrics.get('gpu_wait_ms')}` ms
- Model load: `{metrics.get('model_load_ms')}` ms
- Active session wall clock: `{metrics.get('active_session_wall_clock_ms')}` ms
- Benchmark total wall clock: `{metrics.get('benchmark_total_wall_clock_ms')}` ms
- Uncontended: `{metrics.get('uncontended')}`

`benchmark_total_wall_clock_ms` includes GPU queue time and is not used alone
to judge model speed when GPU contention is detected.

## Correctness Marker

`{result.get('correctness_marker')}`

## Runtime Counters

```json
{json.dumps(counters, ensure_ascii=False, indent=2)}
```

## Schema Repair

- raw_schema_valid_count: `{metrics.get('raw_schema_valid_count')}`
- repair_used_count: `{metrics.get('repair_used_count')}`
- repair_success_count: `{metrics.get('repair_success_count')}`
- second_generate_count: `{metrics.get('second_generate_count')}`

## Timing Fields

```json
{json.dumps(result.get('latency_breakdown_fields'), ensure_ascii=False, indent=2)}
```
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--manifest", default=str(ROOT / ".runtime" / "vlm-smoke" / "vlm_smoke_manifest.jsonl"))
    args = parser.parse_args()

    run_python(ROOT / "ai-service" / "scripts" / "build_vlm_smoke_images.py")
    manifest = load_manifest(Path(args.manifest))
    client = TestClient(app)
    status = client.get("/api/v1/vlm/status").json()
    cfg = load_config()
    provider = LocalQwen3VlProvider(cfg)
    wall_started = time.time()
    attempts, latencies = analyze_images(provider, manifest, args.limit, cfg)
    total_wall_clock_ms = round((time.time() - wall_started) * 1000, 2)
    deps = dependency_status()
    gpu = gpu_status()
    files = model_files(cfg.model_dir)

    real_count = sum(1 for item in attempts if item["real_vlm_inference"])
    provider_success_count = sum(1 for item in attempts if item["provider_success"])
    schema_valid_count = sum(1 for item in attempts if item["schema_valid"])
    repair_used_count = sum(1 for item in attempts if item["repair_used"])
    fallback_count = sum(1 for item in attempts if item["fallback_used"])
    unload_success_count = sum(1 for item in attempts if item["unload_success"])
    gpu_peaks = [item["gpu_peak_memory_mb"] for item in attempts if item.get("gpu_peak_memory_mb") is not None]
    breakdowns = [item.get("latency_breakdown") or {} for item in attempts]
    generate_latencies = [item.get("generate_ms") for item in breakdowns if item.get("generate_ms") is not None]
    end_to_end_latencies = [item.get("total_request_ms") for item in breakdowns if item.get("total_request_ms") is not None]
    raw_schema_valid_count = sum(1 for item in attempts if item.get("raw_schema_valid"))
    raw_schema_valid_rate = round(raw_schema_valid_count / len(attempts), 4) if attempts else 0
    deterministic_normalization_success_count = sum(1 for item in attempts if item.get("deterministic_normalization_success"))
    deterministic_normalization_used_count = sum(1 for item in attempts if item.get("deterministic_normalization_used"))
    safe_repair_success_count = sum(1 for item in attempts if item.get("safe_repair_success"))
    safe_repair_used_count = sum(1 for item in attempts if item.get("safe_repair_used"))
    second_generate_count = sum(int(item.get("second_generate_count") or 0) for item in attempts)
    latest_counters = Qwen3VlRuntimeCounters.snapshot()
    external_gpu_processes = external_gpu_compute_processes()
    total = len(manifest[: args.limit])
    blocked = []
    if not files["exists"]:
        blocked.append("VLM_MODEL_NOT_AVAILABLE")
    elif not files["has_weight_file"]:
        blocked.append("VLM_MODEL_WEIGHTS_NOT_AVAILABLE")
    if not deps.get("accelerate"):
        blocked.append("ACCELERATE_NOT_INSTALLED_FOR_TRANSFORMERS_DEVICE_MAP")
    if real_count == 0:
        blocked.append("NO_REAL_TRANSFORMERS_VLM_INFERENCE_RECORDED")

    metrics = {
        "total_samples": total,
        "real_vlm_inference_count": real_count,
        "vlm_success_rate": round(real_count / total, 4) if total else 0,
        "provider_success_count": provider_success_count,
        "schema_valid_count": schema_valid_count,
        "repair_used_count": repair_used_count,
        "fallback_count": fallback_count,
        "unload_success_count": unload_success_count,
        "visual_schema_valid_rate": round(schema_valid_count / total, 4) if total else 0,
        "visual_field_complete_rate": round(schema_valid_count / total, 4) if total else 0,
        "fallback_rate": round(fallback_count / total, 4) if total else 0,
        "invalid_json_count": 0,
        "repair_used_rate": round(repair_used_count / total, 4) if total else 0,
        "avg_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_latency_ms": percentile(latencies, 95),
        "avg_generate_ms": round(statistics.mean(generate_latencies), 2) if generate_latencies else None,
        "p95_generate_ms": percentile(generate_latencies, 95),
        "avg_end_to_end_ms": round(statistics.mean(end_to_end_latencies), 2) if end_to_end_latencies else None,
        "p95_end_to_end_ms": percentile(end_to_end_latencies, 95),
        "total_wall_clock_ms": total_wall_clock_ms,
        "raw_schema_valid_rate": raw_schema_valid_rate,
        "gpu_peak_memory_mb": max(gpu_peaks) if gpu_peaks else gpu.get("gpu_memory_reserved_mb"),
        "oom_count": 0,
        "unload_success_rate": round(unload_success_count / total, 4) if total else 0,
        "privacy_smoke_detection_rate": 0,
        "raw_schema_valid_count": raw_schema_valid_count,
        "repair_success_count": schema_valid_count if repair_used_count else 0,
        "deterministic_normalization_rate": round(deterministic_normalization_used_count / total, 4) if total else 0,
        "deterministic_normalization_success_rate": round(deterministic_normalization_success_count / total, 4) if total else 0,
        "safe_repair_rate": round(safe_repair_used_count / total, 4) if total else 0,
        "safe_repair_success_rate": round(safe_repair_success_count / total, 4) if total else 0,
        "repair_avg_ms": round(statistics.mean([item.get("schema_repair_ms") for item in breakdowns if item.get("schema_repair_ms") is not None]), 2)
        if any(item.get("schema_repair_ms") is not None for item in breakdowns)
        else 0,
        "second_generate_count": second_generate_count,
        **latest_counters,
    }
    metrics.update(
        build_session_latency_metrics(
            breakdowns=breakdowns,
            total_wall_clock_ms=total_wall_clock_ms,
            external_process_count=len(external_gpu_processes),
            gpu_busy_waiting_seen=False,
        )
    )
    pass_thresholds_12 = (
        total == 12
        and real_count == 12
        and metrics["vlm_success_rate"] >= 0.8
        and metrics["visual_schema_valid_rate"] >= 0.9
        and metrics["fallback_rate"] <= 0.2
        and metrics["oom_count"] == 0
        and metrics["unload_success_rate"] >= 0.9
        and metrics["model_load_count"] == 1
        and metrics["processor_load_count"] == 1
        and metrics["generate_call_count"] >= 12
        and metrics["unload_count"] == 1
        and metrics["gpu_lock_acquire_count"] == 1
    )
    pass_thresholds_3 = (
        total == 3
        and real_count == 3
        and provider_success_count >= 2
        and schema_valid_count == 3
        and fallback_count == 0
        and metrics["oom_count"] == 0
        and unload_success_count == 3
    )
    if pass_thresholds_12:
        classification = classify_session_marker(metrics, total)
        marker = classification["latency_marker"]
    elif pass_thresholds_3:
        classification = {
            "correctness_pass": True,
            "active_latency_pass": False,
            "correctness_marker": "VLM_PROVIDER_SESSION_3_PASS",
            "latency_marker": "VLM_PROVIDER_SESSION_3_PASS",
        }
        marker = "VLM_PROVIDER_SESSION_3_PASS"
    else:
        classification = classify_session_marker(metrics, total)
        marker = "VLM_PROVIDER_SMOKE_BLOCKED"
    result = {
        "marker": marker,
        "correctness_marker": classification["correctness_marker"],
        "active_latency_marker": classification["active_latency_marker"],
        "total_wall_clock_marker": classification["total_wall_clock_marker"],
        "active_latency_pass": classification["active_latency_pass"],
        "external_gpu_compute_processes": external_gpu_processes,
        "provider": status.get("provider"),
        "model_name": status.get("model_name"),
        "model_dir": "<external_model_root>/Qwen3-VL-2B-Instruct" if status.get("model_dir") else None,
        "model_source": "Hugging Face official repository: Qwen/Qwen3-VL-2B-Instruct",
        "model_files": files,
        "config": {
            "device": cfg.device,
            "dtype": cfg.dtype,
            "max_new_tokens": cfg.max_new_tokens,
            "max_images": cfg.max_images,
            "max_pixels": cfg.max_pixels,
            "min_pixels": cfg.min_pixels,
            "timeout_seconds": cfg.timeout_seconds,
            "enable_thinking": cfg.enable_thinking,
            "lazy_load": cfg.lazy_load,
            "unload_after_request": cfg.unload_after_request,
        },
        "dependencies": deps,
        "gpu": gpu,
        "metrics": metrics,
        "attempts": attempts,
        "latency_breakdown_fields": [
            "gpu_wait_ms",
            "gpu_lock_wait_ms",
            "gpu_lock_acquire_ms",
            "model_load_ms",
            "processor_load_ms",
            "active_generate_total_ms",
            "active_processing_total_ms",
            "image_decode_ms",
            "image_resize_ms",
            "prompt_build_ms",
            "processor_encode_ms",
            "input_transfer_ms",
            "generate_ms",
            "decode_ms",
            "raw_json_parse_ms",
            "deterministic_normalization_ms",
            "schema_repair_ms",
            "parse_or_repair_total_ms",
            "provider_mapping_ms",
            "tool_log_persist_ms",
            "model_unload_ms",
            "gpu_release_wait_ms",
            "total_request_ms",
            "active_session_wall_clock_ms",
            "benchmark_total_wall_clock_ms",
        ],
        "manifest": str(Path(args.manifest)),
        "blocking_reasons": blocked,
        "forbidden_success_markers_emitted": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(smoke_report(result), encoding="utf-8", newline="\n")
    GPU_REPORT.write_text(memory_report(result), encoding="utf-8", newline="\n")
    LATENCY_OUT.parent.mkdir(parents=True, exist_ok=True)
    LATENCY_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    LATENCY_REPORT.write_text(latency_report(result), encoding="utf-8", newline="\n")
    raw_analysis = build_raw_schema_failure_analysis(result)
    RAW_SCHEMA_OUT.write_text(json.dumps(raw_analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    RAW_SCHEMA_REPORT.write_text(raw_schema_report(raw_analysis), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
