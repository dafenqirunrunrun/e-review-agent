import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_v2.service import RagV2Service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()
    service = RagV2Service()
    if args.status_only:
        print(json.dumps(service.status(), ensure_ascii=False))
        return 0
    try:
        metadata = service.build_index()
    except RuntimeError as exc:
        print(str(exc))
        print("RAG_INDEX_BUILD_BLOCKED")
        return 2
    summary = {key: value for key, value in metadata.items() if key not in {"cases", "case_ids"}}
    print(json.dumps(summary, ensure_ascii=False))
    print("RAG_INDEX_BUILD_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
