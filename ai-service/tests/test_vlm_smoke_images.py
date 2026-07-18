import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_vlm_smoke_image_builder_creates_synthetic_manifest():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/build_vlm_smoke_images.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert "VLM_SMOKE_IMAGES_READY" in completed.stdout
    manifest_path = ROOT / ".runtime/vlm-smoke/vlm_smoke_manifest.jsonl"
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 12
    assert all(row["source_type"] == "synthetic_smoke" for row in rows)
    assert all("real_external_eval" in row["forbidden_use"] for row in rows)
    assert all("sft_training" in row["forbidden_use"] for row in rows)
    assert all("rag_indexing" in row["forbidden_use"] for row in rows)
    assert all((ROOT / row["image_path"]).exists() for row in rows)


def test_vlm_smoke_outputs_are_gitignored():
    completed = subprocess.run(
        ["git", "check-ignore", ".runtime/vlm-smoke/vlm_smoke_manifest.jsonl"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ".runtime/vlm-smoke/vlm_smoke_manifest.jsonl" in completed.stdout
