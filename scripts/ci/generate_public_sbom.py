from __future__ import annotations

import json
from pathlib import Path

from public_runtime_common import ROOT, main_guard, run_command


def main() -> None:
    output_dir = ROOT / "artifacts" / "operations" / "v1.9.0-phase3" / "sbom"
    output_dir.mkdir(parents=True, exist_ok=True)
    images = {
        "backend": "e-review-agent-public-backend:v190-phase2",
        "ai-service": "e-review-agent-public-ai-service:v190-phase2",
        "admin": "e-review-agent-public-admin:v190-phase2",
        "customer": "e-review-agent-public-customer:v190-phase2",
    }
    manifest = {}
    for name, image in images.items():
        output = output_dir / f"{name}.spdx.json"
        run_command(["trivy", "image", "--format", "spdx-json", "--output", str(output), image])
        manifest[name] = str(output.relative_to(ROOT))
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("PUBLIC_SBOM_PASS")


if __name__ == "__main__":
    main_guard(main)
