from __future__ import annotations

import hashlib
import inspect
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts import run_step213a1_gpu_qwen_benchmark as gpu
from scripts import run_step213a_lite as cpu


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213a1_gpu"
GATE = OUTPUT / "step213a1_gpu_gate_v1.json"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_gpu_environment_isolated():
    assert gpu.GPU_ENV.is_dir()
    assert gpu.CPU_ENV.is_dir()
    assert gpu.GPU_ENV.resolve() != gpu.CPU_ENV.resolve()
    assert "include-system-site-packages = false" in (gpu.GPU_ENV / "pyvenv.cfg").read_text(encoding="utf-8")
    assert "ai-service/.venv-qwen-gpu/" in (gpu.REPO_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_runtime_env_not_modified():
    script = "import json,torch,transformers,pydantic;print(json.dumps([torch.__version__,torch.cuda.is_available(),transformers.__version__,pydantic.__version__]))"
    values = json.loads(subprocess.check_output([str(gpu.CPU_ENV / "Scripts" / "python.exe"), "-c", script], text=True))
    assert values == ["2.14.0+cpu", False, "5.16.1", "2.7.4"]


def test_cuda_model_device():
    snapshot = read_json("local_qwen_gpu_model_snapshot_v1.json")
    environment = read_json("gpu_environment_audit_v1.json")
    assert environment["gpuPython"]["cudaAvailable"] is True
    assert snapshot["device"].startswith("cuda")
    assert snapshot["dtype"] == "bfloat16"
    assert snapshot["quantized"] is False and snapshot["cpuOffload"] is False


def test_same_prompt_as_cpu_probe():
    prompt_hash = hashlib.sha256(gpu.PROMPT_PATH.read_bytes()).hexdigest().upper()
    gpu_snapshot = read_json("local_qwen_gpu_model_snapshot_v1.json")
    cpu_snapshot = json.loads(gpu.CPU_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert prompt_hash == gpu.EXPECTED_PROMPT_HASH == gpu_snapshot["promptHash"] == cpu_snapshot["promptHash"]
    assert gpu_snapshot["generationConfigHash"] == cpu_snapshot["generationConfigHash"]


def test_same_probe_case_ids():
    cpu_ids = tuple(row["caseId"] for row in cpu.load_jsonl(gpu.CPU_OUTPUT_PATH))
    probe = read_json("gpu_latency_probe_v1.json")
    assert cpu_ids == gpu.PROBE_CASE_IDS == tuple(probe["caseIds"])


def test_20case_fixed_sample():
    metrics = read_json("gpu_20case_checkpoint_metrics_v1.json")
    outputs = cpu.load_jsonl(OUTPUT / "gpu_20case_checkpoint_outputs_v1.jsonl")
    assert tuple(metrics["caseIds"]) == gpu.CHECKPOINT_CASE_IDS
    assert tuple(row["caseId"] for row in outputs) == gpu.CHECKPOINT_CASE_IDS
    assert set(metrics["coverage"]) == {"normal", "explicit", "implicit", "multi-risk", "hard", "hard-negative", "ambiguous", "noisy"}


def test_20case_gate():
    metrics = read_json("gpu_20case_checkpoint_metrics_v1.json")
    expected = "PASS" if all(metrics["conditions"].values()) else "FAIL"
    gate = read_json("step213a1_gpu_gate_v1.json")
    assert metrics["gate"] == expected == gate["localQwen20CaseQualityGate"]


def test_frozen_not_executed():
    gate = read_json("step213a1_gpu_gate_v1.json")
    assert cpu.sha256_file(cpu.DEFAULT_FROZEN) == cpu.FROZEN_GOLD_SHA
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == cpu.FROZEN_GOLD_SHA


def test_external_api_zero():
    gate = read_json("step213a1_gpu_gate_v1.json")
    snapshot = read_json("local_qwen_gpu_model_snapshot_v1.json")
    source = inspect.getsource(gpu.configure_offline_gpu_provider)
    assert gate["externalApiCallCount"] == snapshot["externalApiCallCount"] == 0
    assert '"HF_HUB_OFFLINE": "1"' in source
    assert "local://transformers" in source


@dataclass
class FakeResult:
    content: str
    latency_ms: int = 5
    token_usage_input: int = 10
    token_usage_output: int = 5


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt: str) -> FakeResult:
        self.calls += 1
        return FakeResult(json.dumps({"decision": "CLASSIFY", "riskTypes": ["normal_review"], "severity": "LOW", "confidenceBand": "HIGH", "needsHumanReview": False, "reasonCodes": ["NORMAL"]}))


def test_gpu_cache_resume(tmp_path):
    provider = FakeProvider()
    kwargs = dict(provider=provider, prompt="same", case_id="same", dataset_hash="same", model_identity="same", prompt_hash="same", cache_dir=tmp_path)
    first = cpu.invoke_local_qwen(**kwargs)
    second = cpu.invoke_local_qwen(**kwargs)
    assert first["cacheHit"] is False
    assert second["cacheHit"] is True
    assert provider.calls == 1


def test_gpu_metrics():
    probe = read_json("gpu_latency_probe_v1.json")
    checkpoint = read_json("gpu_20case_checkpoint_metrics_v1.json")
    snapshot = read_json("local_qwen_gpu_model_snapshot_v1.json")
    assert probe["caseCount"] == 5
    assert checkpoint["qwen"]["caseCount"] == 20
    assert 0 <= checkpoint["qwen"]["schemaCompliance"] <= 1
    assert snapshot["memory"]["peakAllocatedVramMiB"] > 0
    assert snapshot["contextAllocationBounded"] is True


def test_runtime_services_unchanged():
    gate = read_json("step213a1_gpu_gate_v1.json")
    assert gate["runtimeServicesGate"] == "PASS"


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [gpu.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
