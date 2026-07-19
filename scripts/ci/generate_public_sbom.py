from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from public_runtime_common import ROOT, main_guard, run_command


def _source_commit() -> str:
    return os.getenv("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _tool_version() -> str:
    proc = run_command(["trivy", "--version"])
    return proc.stdout.splitlines()[0].strip()


def _image_digest(image: str) -> str:
    proc = run_command(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    digest = proc.stdout.strip()
    if not digest.startswith("sha256:"):
        raise RuntimeError(f"image digest was not sha256 for {image}: {digest}")
    return digest


def main() -> None:
    output_dir = ROOT / "artifacts" / "operations" / "v1.9.0-phase3" / "sbom"
    output_dir.mkdir(parents=True, exist_ok=True)
    images = {
        "backend": "e-review-agent-public-backend:v190-phase2",
        "ai-service": "e-review-agent-public-ai-service:v190-phase2",
        "admin": "e-review-agent-public-admin:v190-phase2",
        "customer": "e-review-agent-public-customer:v190-phase2",
    }
    manifest = {
        "schemaVersion": "public-sbom-manifest-v2",
        "sourceCommit": _source_commit(),
        "workflowRunId": os.getenv("GITHUB_RUN_ID", "local"),
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": "PASS",
        "tool": "trivy",
        "toolVersion": _tool_version(),
        "images": {},
        "checks": {
            "imageCount": 4,
            "sbomFilesPresent": True,
        },
        "boundaries": ["PRODUCTION_READY_NOT_CLAIMED"],
    }
    for name, image in images.items():
        output = output_dir / f"{name}.spdx.json"
        run_command(["trivy", "image", "--format", "spdx-json", "--output", str(output), image])
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError(f"SBOM output missing or empty: {output}")
        manifest["images"][name] = {
            "image": image,
            "imageDigest": _image_digest(image),
            "sbomPath": str(output.relative_to(ROOT)),
            "sbomSha256": _sha256(output),
        }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("PUBLIC_SBOM_PASS")


if __name__ == "__main__":
    main_guard(main)
