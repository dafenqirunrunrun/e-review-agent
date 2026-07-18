import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def test_v170_enterprise_eval_dataset_generation_and_gates():
    gen = subprocess.run(
        [PYTHON, "ai-service/scripts/generate_v170_enterprise_eval_dataset.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "V170_ENTERPRISE_EVAL_DATASET_PASS" in gen.stdout
    gate = subprocess.run(
        [PYTHON, "ai-service/scripts/eval_v170_enterprise_gates.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "V170_ENTERPRISE_RAG_AGENT_ENGINEERING_GATE_PASS" in gate.stdout
    audit = json.loads((ROOT / "data/private_research/audit/v170_enterprise_quality_gates.json").read_text(encoding="utf-8"))
    assert audit["rag"]["status"] == "V170_RAG_QUALITY_GATE_PASS"
    assert audit["agent"]["prohibited_tool_call_count"] == 0
    assert audit["adapter_runtime"]["status"] == "V170_ADAPTER_RUNTIME_GATE_PASS"
