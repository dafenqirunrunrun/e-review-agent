import json
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ai-service/scripts/v161_unblock_prerequisites.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("v161_unblock_prerequisites", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v161_unblock_prerequisites_reports_missing_real_data_without_failing():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert "V161_UNBLOCK_PREREQUISITES_BLOCKED" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/audit/v161_unblock_prerequisites.json").read_text(encoding="utf-8"))
    statuses = {item["name"]: item["status"] for item in result["checks"]}
    assert statuses["real_text_source_file"] == "BLOCKED"
    assert statuses["local_vlm_model"] in {"READY", "BLOCKED"}
    assert statuses["private_data_not_tracked"] == "READY"
    assert statuses["model_weights_not_tracked"] == "READY"


def test_v161_unblock_prerequisites_accepts_repo_external_path_overrides(tmp_path):
    module = load_script_module()
    real_json = tmp_path / "data-private" / "banglishrev" / "reviews v1.json"
    vlm_dir = tmp_path / "models" / "Qwen3-VL-2B-Instruct"
    text_model_dirs = [
        tmp_path / "models" / "bge-m3",
        tmp_path / "models" / "rag-reranker",
        tmp_path / "models" / "Qwen3-1.7B",
    ]
    real_json.parent.mkdir(parents=True)
    real_json.write_text("[]\n", encoding="utf-8")
    vlm_dir.mkdir(parents=True)
    (vlm_dir / "config.json").write_text("{}\n", encoding="utf-8")
    (vlm_dir / "tokenizer_config.json").write_text("{}\n", encoding="utf-8")
    (vlm_dir / "model.safetensors").write_bytes(b"placeholder")
    for directory in text_model_dirs:
        directory.mkdir(parents=True)

    result = module.build_result(
        str(real_json),
        [str(vlm_dir)],
        [str(directory) for directory in text_model_dirs],
        sys.executable,
    )

    statuses = {item["name"]: item["status"] for item in result["checks"]}
    assert statuses["real_text_source_file"] == "READY"
    assert statuses["local_vlm_model"] == "READY"
    assert statuses["existing_text_models"] == "READY"
    assert result["inputs"]["real_json"] == str(real_json)
