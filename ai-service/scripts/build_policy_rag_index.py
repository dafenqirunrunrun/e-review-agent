from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import DEFAULT_INDEX_DIR, build_policy_index
from app.policy_rag.parser import PolicyDocumentParser
from app.policy_rag.seeds import seed_policy_documents


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the structure-aware policy RAG JSONL index.")
    parser.add_argument("--output-dir", default=str(DEFAULT_INDEX_DIR), help="Directory for policy_chunks.jsonl and policy_manifest.json.")
    parser.add_argument(
        "--sources-json",
        default="",
        help="Optional JSON file with local policy source specs. If omitted, bundled public seed sources are indexed.",
    )
    parser.add_argument("--no-dense", action="store_true", help="Skip optional Qwen embedding + FAISS index build.")
    parser.add_argument("--review-relevant-only", action="store_true", help="Index only chunks relevant to review governance.")
    args = parser.parse_args()

    documents = _load_documents(Path(args.sources_json)) if args.sources_json else seed_policy_documents()
    manifest = build_policy_index(
        documents,
        output_dir=Path(args.output_dir),
        build_dense=not args.no_dense,
        review_relevant_only=args.review_relevant_only,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "schemaVersion": manifest["schemaVersion"],
                "chunkCount": manifest["chunkCount"],
                "sourceCount": manifest["sourceCount"],
                "chunkPath": manifest["chunkPath"],
                "indexHash": manifest["indexHash"],
                "denseStatus": manifest.get("retrieval", {}).get("dense", {}).get("status", "unknown"),
                "denseFallbackReason": manifest.get("retrieval", {}).get("dense", {}).get("fallbackReason", ""),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _load_documents(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    parser = PolicyDocumentParser()
    documents = []
    for item in data:
        source_file = item.get("path")
        common = {
            "source_id": item["sourceId"],
            "source_url": item["sourceUrl"],
            "source_name": item["sourceName"],
            "source_type": item["sourceType"],
            "language": item.get("language", "en"),
            "jurisdiction": item.get("jurisdiction", "platform"),
            "license_class": item.get("licenseClass", "public_reference_restricted"),
        }
        if source_file:
            document = parser.parse_file(Path(source_file), **common)
        else:
            document = parser.parse_text(content=item["content"], **common)
        document.manifest.metadata.update(
            {
                key: item[key]
                for key in ("fetchedAt", "httpContentType", "rawContentHash")
                if key in item
            }
        )
        documents.append(document)
    return documents


if __name__ == "__main__":
    raise SystemExit(main())
