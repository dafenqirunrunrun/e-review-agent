import json
from pathlib import Path
from typing import Dict, List


REQUIRED_CASE_FIELDS = {
    "case_id", "title", "product_category", "risk_type", "risk_level", "scenario",
    "evidence", "operation_suggestion", "human_review_reason", "tags", "source_type",
}


def load_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def load_cases(path: Path) -> List[Dict]:
    rows = load_jsonl(path)
    seen = set()
    for row in rows:
        missing = REQUIRED_CASE_FIELDS - set(row)
        if missing:
            raise ValueError(f"case fields missing: {sorted(missing)}")
        case_id = row["case_id"]
        if case_id in seen:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
    return rows


def case_text(row: Dict) -> str:
    evidence = " ".join(str(value) for value in row.get("evidence") or [])
    tags = " ".join(str(value) for value in row.get("tags") or [])
    return f"{row.get('title', '')} {row.get('scenario', '')} {evidence} {tags}".strip()
