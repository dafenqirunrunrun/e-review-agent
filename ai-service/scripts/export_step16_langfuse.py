"""Optional, fail-open Langfuse v4 mirror for the frozen Step 16 corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.observability.langfuse_sidecar import _safe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data/benchmarks/review_governance_gold_v1.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mirror_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "caseId": row["caseId"],
            "input": _safe({"reviewText": row["reviewText"], "rating": row["rating"]}),
            "expectedOutput": {
                "riskTypes": row["expectedRiskTypes"], "route": row["expectedRoute"],
                "decision": row["expectedDecision"], "reflection": row["expectedEvidenceStatus"],
            },
        }
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a sanitized Langfuse mirror of frozen Step 16 gold.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/langfuse/frozen_dataset_mirror.json")
    parser.add_argument("--expected-gold-sha256", default="")
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    sha = hashlib.sha256(raw).hexdigest().upper()
    if args.expected_gold_sha256 and sha != args.expected_gold_sha256.upper():
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={args.expected_gold_sha256.upper()} actual={sha}")
    rows = read_jsonl(args.dataset)
    mirror = {"datasetName": "e-review-governance-frozen-v1", "goldSha256": sha, "caseCount": len(rows), "items": mirror_rows(rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(mirror, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    exported = False
    error = ""
    if os.getenv("LANGFUSE_ENABLED", "false").lower() == "true" and os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import Langfuse
            client = Langfuse(base_url=os.environ["LANGFUSE_HOST"], public_key=os.environ["LANGFUSE_PUBLIC_KEY"], secret_key=os.environ["LANGFUSE_SECRET_KEY"])
            dataset_name = mirror["datasetName"]
            client.create_dataset(name=dataset_name, description="Sanitized mirror; frozen gold remains the source of truth.", metadata={"goldSha256": sha, "caseCount": str(len(rows))})
            for item in mirror["items"]:
                client.create_dataset_item(dataset_name=dataset_name, input=item["input"], expected_output=item["expectedOutput"], metadata={"caseId": item["caseId"], "goldSha256": sha})
            client.flush()
            exported = True
        except Exception as exc:
            error = type(exc).__name__
    print(json.dumps({"caseCount": len(rows), "goldSha256": sha, "localMirror": str(args.output), "langfuseExported": exported, "langfuseError": error}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
