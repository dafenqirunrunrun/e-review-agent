#!/usr/bin/env python
"""Generate deterministic synthetic knowledge for scale qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


TOPICS = [
    ("after_sales", "refund replacement warranty broken damaged"),
    ("logistics", "shipping delivery delay tracking package"),
    ("review_risk", "fake review prompt injection pii harassment"),
    ("quality", "battery screen fabric size material"),
    ("policy", "return policy evidence citation tenant"),
    ("neutral", "usage guide product description care"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(index: int, tenants: int, rng: random.Random) -> dict[str, object]:
    topic, keywords = TOPICS[index % len(TOPICS)]
    tenant = f"tenant-{index % tenants:03d}"
    active = index % 17 != 0
    expired = index % 23 == 0
    duplicate_group = f"dup-{index // 10:05d}" if index % 97 in (0, 1) else None
    language = "zh" if index % 3 == 0 else "en"
    synonym = "退换货 售后 风险 证据" if language == "zh" else "return support risk evidence"
    filler = " ".join(rng.choice(keywords.split()) for _ in range(8 + (index % 9)))
    return {
        "chunkId": f"chunk-{index:07d}",
        "documentId": f"doc-{index // 5:07d}",
        "tenantId": tenant,
        "visibility": "tenant" if index % 5 else "public",
        "active": active,
        "expired": expired,
        "topic": topic,
        "language": language,
        "duplicateGroup": duplicate_group,
        "text": f"{topic} {keywords} {synonym} {filler} stable synthetic evidence {index}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=int, required=True)
    parser.add_argument("--tenants", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2100)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    topic_counts: dict[str, int] = {}
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for index in range(args.chunks):
            record = _record(index, args.tenants, rng)
            topic_counts[str(record["topic"])] = topic_counts.get(str(record["topic"]), 0) + 1
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "datasetVersion": "v2.1-scale-synthetic-v1",
        "generatedAt": _utc_now(),
        "chunkCount": args.chunks,
        "documentCount": (args.chunks + 4) // 5,
        "tenantCount": args.tenants,
        "seed": args.seed,
        "topicCounts": topic_counts,
        "hash": _sha256_file(output),
        "syntheticOnly": True,
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SCALE_KNOWLEDGE_GENERATED chunks={args.chunks} manifest={manifest_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
