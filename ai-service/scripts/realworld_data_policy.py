import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
REAL_DATA_DIR = Path(os.getenv("E_REVIEW_REAL_DATA_DIR", r"D:\EReviewAgent\data-private\realworld"))
REAL_MANIFEST_DIR = Path(os.getenv("E_REVIEW_REAL_DATA_MANIFEST_DIR", ROOT / "data" / "real_world"))

APPROVED_SOURCES = REAL_MANIFEST_DIR / "source_manifest" / "approved_sources.jsonl"
DELEGATED_APPROVED_SOURCES = REAL_MANIFEST_DIR / "source_manifest" / "delegated_approved_sources.jsonl"
SOURCE_AUDIT = REAL_MANIFEST_DIR / "audit" / "source_license_audit.json"

TEXT_SCHEMA_REQUIRED = {
    "sample_id",
    "source_id",
    "source_record_id_hash",
    "source_language",
    "product_category",
    "rating",
    "review_text",
    "review_text_redacted",
    "image_available",
    "image_ids",
    "source_type",
    "privacy_status",
    "annotation_status",
    "split",
    "created_at",
    "processing_version",
}

PII_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"\b\d{6,}\b"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"(address|phone|mobile|tracking|express|order)\s*[:：-]?\s*\S+", re.I),
    re.compile(r"(地址|手机号|电话|快递单|订单号)\s*[:：-]?\s*\S+"),
]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def approved_sources() -> list[dict]:
    explicit_sources = [
        row
        for row in load_jsonl(APPROVED_SOURCES)
        if row.get("approval_status") == "approved"
        and row.get("research_use_allowed") is True
    ]
    delegated_sources = [
        row
        for row in load_jsonl(DELEGATED_APPROVED_SOURCES)
        if row.get("decision_status") == "conditionally_approved"
        and row.get("approval_scope") in {"private_internal_pilot", "auxiliary_development_only"}
        and row.get("research_use_allowed") is True
    ]
    by_id = {row.get("source_id"): row for row in explicit_sources + delegated_sources}
    return [row for row in by_id.values() if row.get("source_id")]


def source_by_id(source_id: str) -> dict | None:
    return next((row for row in approved_sources() if row.get("source_id") == source_id), None)


def stable_hash(value: str, prefix: str = "") -> str:
    digest = hashlib.sha256((prefix + value).encode("utf-8")).hexdigest()
    return digest


def redact_text(text: str) -> tuple[str, int]:
    redacted = text or ""
    count = 0
    for pattern in PII_PATTERNS:
        redacted, hits = pattern.subn("[REDACTED]", redacted)
        count += hits
    return redacted, count


def blocked_result(marker: str, reason: str, **extra) -> dict:
    payload = {"marker": marker, "blocking_reasons": [reason], **extra}
    return payload


def ensure_private_dirs() -> None:
    for name in [
        "sources",
        "raw-text",
        "raw-images",
        "processed-text",
        "processed-images",
        "annotations",
        "external-test",
        "audit-cache",
    ]:
        (REAL_DATA_DIR / name).mkdir(parents=True, exist_ok=True)
