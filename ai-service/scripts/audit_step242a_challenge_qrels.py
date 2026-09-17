from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.audit import audit_legacy_challenge_qrels
from scripts.build_step242a_rag_quality_v2 import CHUNKS, LEGACY_DATASET, LEGACY_MANIFEST, load_jsonl, write_json


DEFAULT_OUTPUT = ROOT / "artifacts" / "step242a" / "legacy_challenge_qrels_audit.json"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audit existing Step 23.3C pooled qrels without changing them.")
    parser.add_argument("--dataset", type=Path, default=LEGACY_DATASET)
    parser.add_argument("--manifest", type=Path, default=LEGACY_MANIFEST)
    parser.add_argument("--chunks", type=Path, default=CHUNKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = audit_legacy_challenge_qrels(
        load_jsonl(args.dataset.resolve()),
        load_policy_chunks(args.chunks.resolve()),
        json.loads(args.manifest.resolve().read_text(encoding="utf-8-sig")),
    )
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output.resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["missingChunkReferences"] and not report["duplicateCaseIds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
