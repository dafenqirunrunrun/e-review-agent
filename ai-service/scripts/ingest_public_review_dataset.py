import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ID = "banglishrev_hf_2024"
PRIVATE_DEFAULT = Path("D:/EReviewAgent/data-private/banglishrev/reviews v1.json")
STAGING_PATH = ROOT / "data/real_world/processed/real_reviews_staging.jsonl"
REPORT_PATH = ROOT / "docs/109_v161_real_data_source_and_license_report.md"


def sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def iter_top_level_objects(path: Path) -> Iterator[Dict]:
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        buffer = ""
        inside_array = False
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            buffer += chunk
            while buffer:
                stripped = buffer.lstrip()
                if not inside_array:
                    if not stripped:
                        buffer = ""
                        break
                    if stripped[0] != "[":
                        raise ValueError("EXPECTED_TOP_LEVEL_JSON_ARRAY")
                    inside_array = True
                    buffer = stripped[1:]
                    continue
                stripped = buffer.lstrip()
                if not stripped:
                    buffer = ""
                    break
                if stripped[0] == ",":
                    buffer = stripped[1:]
                    continue
                if stripped[0] == "]":
                    return
                try:
                    obj, index = decoder.raw_decode(stripped)
                except json.JSONDecodeError:
                    break
                yield obj
                buffer = stripped[index:]


def redact_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"1[3-9]\d{9}", "[PHONE]", text)
    text = re.sub(r"\b\d{8,}\b", "[LONG_ID]", text)
    text = re.sub(r"(订单号|快递单号|地址|电话|手机号)[:：]?\s*\S+", r"\1:[REDACTED]", text)
    return text.strip()


def category_from_product(product: Dict) -> str:
    for key in ("Category", "Product Category", "category", "Product Type"):
        value = product.get(key)
        if value:
            return str(value)[:40]
    return "unknown"


def weak_risk_from_text(text: str, rating: Optional[int]) -> Dict:
    lower = text.lower()
    high_words = ["refund", "fake", "broken", "damage", "missing", "wrong", "not original", "leak", "ভাঙ্গা", "নকল"]
    negative_words = ["bad", "poor", "not good", "problem", "issue", "খারাপ"]
    if any(word in lower for word in high_words) or (rating is not None and rating <= 1):
        return {"risk_type": "after_sales_risk", "risk_level": "high", "need_human_review": True}
    if any(word in lower for word in negative_words) or (rating is not None and rating <= 3):
        return {"risk_type": "negative_review", "risk_level": "medium", "need_human_review": True}
    return {"risk_type": "normal_review", "risk_level": "low", "need_human_review": False}


def rows_from_source(path: Path, limit: int, source_id: str) -> List[Dict]:
    rows: List[Dict] = []
    for product_index, product in enumerate(iter_top_level_objects(path), start=1):
        reviews = product.get("Reviews") or []
        category = category_from_product(product)
        product_hash = sha256_text(json.dumps({k: product.get(k) for k in ("Product ID", "Product Name", "URL")}, ensure_ascii=False, sort_keys=True))
        for review_index, review in enumerate(reviews, start=1):
            text = redact_text(str(review.get("Review Content") or ""))
            if not text:
                continue
            try:
                rating = int(float(review.get("Current Rating"))) if review.get("Current Rating") is not None else None
            except (TypeError, ValueError):
                rating = None
            images = review.get("Images") or []
            risk = weak_risk_from_text(text, rating)
            raw_id = f"{product_index}:{review_index}:{review.get('Buyer ID','')}"
            rows.append({
                "sample_id": f"REAL-BANGLISHREV-{len(rows) + 1:06d}",
                "source_id": source_id,
                "original_record_id_hash": sha256_text(raw_id),
                "product_record_hash": product_hash,
                "product_category": category,
                "rating": rating,
                "review_text": text,
                "image_available": bool(images),
                "image_ids": [sha256_text(str(item))[:24] for item in images],
                "risk_type": risk["risk_type"],
                "risk_level": risk["risk_level"],
                "need_human_review": risk["need_human_review"],
                "evidence_spans": [],
                "expected_action": "待人工标注确认",
                "annotation_status": "weak_heuristic_needs_human_review",
                "source_type": "real_world_public_review",
                "split": "staging",
                "privacy_status": "text_redacted_image_not_downloaded",
            })
            if len(rows) >= limit:
                return rows
    return rows


def update_report(message: str) -> None:
    existing = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else "# v1.6.1 真实数据来源与许可证报告\n"
    marker = "\n## BanglishRev 本地导入状态\n\n"
    section = marker + message.strip() + "\n"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip() + "\n" + section
    else:
        existing = existing.rstrip() + "\n" + section
    REPORT_PATH.write_text(existing, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=PRIVATE_DEFAULT)
    parser.add_argument("--limit", type=int, default=800)
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    args = parser.parse_args()
    if not args.source.exists():
        result = {
            "marker": "PUBLIC_REAL_DATA_LOCAL_SOURCE_BLOCKED",
            "source": str(args.source),
            "reason": "official JSON file is not available in a repository-external path",
        }
        update_report(
            f"`PUBLIC_REAL_DATA_LOCAL_SOURCE_BLOCKED`：尚未在仓库外提供官方 `reviews v1.json`。建议手动下载到 `data-private/banglishrev/` 后运行导入脚本；本轮不自动下载 2GB 原始文件。"
        )
        print(json.dumps(result, ensure_ascii=False))
        print(result["marker"])
        return 0
    rows = rows_from_source(args.source, args.limit, args.source_id)
    write_jsonl(STAGING_PATH, rows)
    result = {"marker": "PUBLIC_REAL_DATA_INGEST_COMPLETE", "staging_count": len(rows), "output": str(STAGING_PATH)}
    update_report(f"`PUBLIC_REAL_DATA_INGEST_COMPLETE`：已从仓库外官方 JSON 生成 staging 样本 {len(rows)} 条。该数据仍为弱启发式标签，必须人工标注后才能用于 PASS 评估。")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
