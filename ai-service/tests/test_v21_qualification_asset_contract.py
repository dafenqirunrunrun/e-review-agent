import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v21_asset_manifest_verifier_blocks_without_local_assets(monkeypatch):
    monkeypatch.delenv("AGENT_RAG_QUALIFICATION_ASSET_MANIFEST", raising=False)
    env = os.environ.copy()
    env.pop("AGENT_RAG_QUALIFICATION_ASSET_MANIFEST", None)
    completed = subprocess.run(
        [sys.executable, "ai-service/scripts/qualification/verify_qualification_asset_manifest.py"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "QUALIFICATION_BGE_ASSET_BLOCKED" in completed.stdout
    assert "QUALIFICATION_DENSE_INDEX_ASSET_BLOCKED" in completed.stdout
    payload = json.loads(
        (ROOT / "artifacts" / "qualification" / "qualification-asset-verification.json").read_text(encoding="utf-8")
    )
    assert payload["status"] == "ASSET_BLOCKED"
    assert payload["reason"] == "AGENT_RAG_QUALIFICATION_ASSET_MANIFEST_NOT_CONFIGURED"
