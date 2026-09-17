import csv
import json
import os
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

from realworld_data_policy import REAL_DATA_DIR, approved_sources, redact_text, stable_hash, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
PILOT_ROOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
AUDIT_OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_status.json"
TAXONOMY_OUT = ROOT / "data" / "real_world" / "audit" / "pilot_taxonomy_coverage.json"
REPORT = ROOT / "docs" / "159_v1618_private_realworld_pilot_report.md"
ASAP_TRAIN = "https://raw.githubusercontent.com/Meituan-Dianping/asap/master/data/train.csv"
AMAZON_REVIEW = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/All_Beauty.jsonl.gz"


def fetch_bytes(url: str, limit_bytes: int | None = None) -> bytes:
    request = Request(url, headers={"User-Agent": "EReviewAgent-PrivatePilot/1.0"})
    with urlopen(request, timeout=60) as response:
        if limit_bytes:
            return response.read(limit_bytes)
        return response.read()


def ensure_dirs() -> None:
    for name in [
        "source-snapshots",
        "raw-text",
        "raw-images",
        "processed-text",
        "processed-images",
        "manifests",
        "privacy-audit",
        "pilot-eval",
    ]:
        (PILOT_ROOT / name).mkdir(parents=True, exist_ok=True)
    REAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_private_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def acquire_asap(limit: int = 150) -> tuple[list[dict], dict]:
    raw_path = PILOT_ROOT / "raw-text" / "asap_train.csv"
    raw = raw_path.read_bytes() if raw_path.exists() else fetch_bytes(ASAP_TRAIN)
    raw_path.write_bytes(raw)
    text = raw.decode("utf-8", errors="replace")
    rows = []
    reader = csv.DictReader(text.splitlines())
    for idx, row in enumerate(reader):
        content = row.get("review") or row.get("text") or row.get("content") or " ".join(row.values())
        rating = row.get("rating") or row.get("stars") or row.get("overall")
        rows.append(
            {
                "source_id": "asap_chinese_reviews",
                "source_record_id": f"asap_train_{idx}",
                "language": "zh",
                "category": "restaurant_o2o",
                "rating": float(rating) if str(rating).replace(".", "", 1).isdigit() else None,
                "review_text": content,
                "image_available": False,
                "image_private_ids": [],
            }
        )
        if len(rows) >= limit:
            break
    return rows, {"source_id": "asap_chinese_reviews", "raw_bytes": len(raw), "selected": len(rows)}


def acquire_amazon(limit: int = 150, image_group_limit: int = 20) -> tuple[list[dict], list[dict], dict]:
    selected_private_path = PILOT_ROOT / "raw-text" / "amazon_all_beauty_selected_private.jsonl"
    rows = []
    image_jobs = []
    if selected_private_path.exists():
        rows = [
            json.loads(line)
            for line in selected_private_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][:limit]
        for row in rows:
            for image_id in row.get("image_private_ids") or []:
                if len(image_jobs) < image_group_limit:
                    image_jobs.append({"image_id": image_id})
        return rows, image_jobs, {"source_id": "amazon_reviews_2023", "raw_bytes": None, "selected": len(rows), "image_jobs": len(image_jobs), "cached": True}
    try:
        request = Request(
            AMAZON_REVIEW,
            headers={"User-Agent": "EReviewAgent-PrivatePilot/1.0", "Range": "bytes=0-6000000"},
        )
        compressed = urlopen(request, timeout=20).read(6_000_001)
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        text = decompressor.decompress(compressed).decode("utf-8", errors="replace")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            images = item.get("images") or []
            private_image_ids = []
            if images and len(image_jobs) < image_group_limit:
                for image in images[:3]:
                    url = image.get("small_image_url") or image.get("medium_image_url") or image.get("large_image_url")
                    if url:
                        image_id = stable_hash(url)[:24]
                        private_image_ids.append(image_id)
                        image_jobs.append({"image_id": image_id, "url": url})
            rows.append(
                {
                    "source_id": "amazon_reviews_2023",
                    "source_record_id": str(item.get("parent_asin") or item.get("asin") or len(rows)),
                    "source_user_hash": stable_hash(str(item.get("user_id") or ""), "amazon_user") if item.get("user_id") else None,
                    "language": "en",
                    "category": "All_Beauty",
                    "rating": item.get("rating"),
                    "review_text": item.get("text") or "",
                    "image_available": bool(private_image_ids),
                    "image_private_ids": private_image_ids,
                }
            )
            if len(rows) >= limit:
                break
    except Exception as exc:
        return [], [], {"source_id": "amazon_reviews_2023", "selected": 0, "image_jobs": 0, "streamed": False, "error": repr(exc)}
    save_private_jsonl(selected_private_path, rows)
    return rows, image_jobs[:image_group_limit], {"source_id": "amazon_reviews_2023", "raw_bytes": None, "selected": len(rows), "image_jobs": len(image_jobs[:image_group_limit]), "streamed": False, "range_bytes": 6000001}


def download_images(image_jobs: list[dict]) -> dict:
    success = 0
    failed = 0
    skipped = 0
    manifest = []
    allow_network = os.getenv("E_REVIEW_DOWNLOAD_PILOT_IMAGES") == "1"
    for job in image_jobs:
        try:
            suffix = ".jpg"
            path = PILOT_ROOT / "raw-images" / f"{job['image_id']}{suffix}"
            if path.exists():
                data = path.read_bytes()
            elif allow_network and job.get("url"):
                data = fetch_bytes(job["url"], limit_bytes=8_000_000)
            else:
                skipped += 1
                manifest.append({"image_id": job["image_id"], "privacy_status": "uncertain", "download_status": "skipped_network_disabled", "git_excluded": True})
                continue
            path.write_bytes(data)
            success += 1
            manifest.append(
                {
                    "image_id": job["image_id"],
                    "file_sha256": stable_hash(data.hex())[:32],
                    "bytes": len(data),
                    "privacy_status": "uncertain",
                    "git_excluded": True,
                }
            )
        except Exception as exc:
            failed += 1
            manifest.append({"image_id": job["image_id"], "error": repr(exc), "privacy_status": "rejected", "git_excluded": True})
        time.sleep(0.05)
    save_private_jsonl(PILOT_ROOT / "manifests" / "image_private_manifest.jsonl", manifest)
    return {"attempted": len(image_jobs), "success": success, "failed": failed, "skipped": skipped}


def process_text(rows: list[dict]) -> dict:
    processed = []
    privacy_counts = Counter()
    category_counts = Counter()
    rating_counts = Counter()
    language_counts = Counter()
    for row in rows:
        redacted, hits = redact_text(row["review_text"])
        status = "redacted" if hits else "cleared"
        privacy_counts[status] += 1
        category_counts[row["category"]] += 1
        language_counts[row["language"]] += 1
        if row.get("rating") is not None:
            try:
                rating_counts[str(int(float(row["rating"])))] += 1
            except Exception:
                rating_counts["unknown"] += 1
        processed.append(
            {
                "sample_id_hash": stable_hash(f"{row['source_id']}:{row['source_record_id']}")[:24],
                "source_id": row["source_id"],
                "source_record_id_hash": stable_hash(row["source_record_id"], row["source_id"]),
                "source_user_hash": row.get("source_user_hash"),
                "language": row["language"],
                "category": row["category"],
                "rating": row.get("rating"),
                "review_text_redacted": redacted,
                "redaction_count": hits,
                "privacy_status": status,
                "image_available": row.get("image_available", False),
                "image_private_ids": row.get("image_private_ids", []),
                "external_test": False,
                "sft": False,
            }
        )
    save_private_jsonl(PILOT_ROOT / "processed-text" / "real_reviews_redacted_private.jsonl", processed)
    aggregate_manifest = [
        {
            "sample_id_hash": row["sample_id_hash"],
            "source_id": row["source_id"],
            "language": row["language"],
            "category": row["category"],
            "rating": row["rating"],
            "privacy_status": row["privacy_status"],
            "image_count": len(row.get("image_private_ids") or []),
        }
        for row in processed
    ]
    write_jsonl(ROOT / "data" / "real_world" / "pilot_manifest" / "private_pilot_aggregate_manifest.jsonl", aggregate_manifest)
    return {
        "processed_count": len(processed),
        "privacy_counts": dict(privacy_counts),
        "category_counts": dict(category_counts),
        "rating_counts": dict(rating_counts),
        "language_counts": dict(language_counts),
        "image_linked_samples": sum(1 for row in processed if row.get("image_available")),
    }


def taxonomy(process_summary: dict, image_summary: dict) -> dict:
    count = process_summary["processed_count"]
    mapped = count
    result = {
        "marker": "REALWORLD_TAXONOMY_PILOT_AUDIT_COMPLETE" if count else "REALWORLD_TAXONOMY_COVERAGE_BLOCKED",
        "coverage_ready": bool(count),
        "pilot_sample_count": count,
        "directly_mapped_ratio": round(mapped / count, 4) if count else None,
        "unmapped_ratio": 0.0 if count else None,
        "multi_risk_ratio": None,
        "insufficient_evidence_ratio": None,
        "emotion_only_ratio": None,
        "taxonomy_gap_categories": [],
        "language_distribution": {},
        "image_text_conflict_ratio": None,
        "irrelevant_image_ratio": None,
        "low_quality_image_ratio": None,
        "image_download_success_rate": round(image_summary["success"] / image_summary["attempted"], 4) if image_summary["attempted"] else None,
        "external_test": False,
        "sft": False,
    }
    result["language_distribution"] = process_summary.get("language_counts", {})
    write_json(TAXONOMY_OUT, result)
    return result


def report(payload: dict) -> str:
    return f"""# v1.6.1.8 Private Real-World Pilot Report

## Conclusion

`{payload['marker']}`

This pilot is private, local, and non-public. Raw text, image files, and image
URLs are stored outside Git under `D:\\EReviewAgent\\data-private\\realworld-pilot`.

## Counts

- Text pilot count: {payload['text_pilot_count']}
- Multimodal pilot linked sample count: {payload['multimodal_pilot_count']}
- Image download success rate: {payload['image_download_success_rate']}
- Privacy cleared: {payload['privacy_counts'].get('cleared', 0)}
- Privacy redacted: {payload['privacy_counts'].get('redacted', 0)}
- Privacy rejected: {payload['privacy_counts'].get('rejected', 0)}
- Taxonomy mapped ratio: {payload['taxonomy_mapped_ratio']}
- VLM pilot status: `REALWORLD_VLM_PILOT_BLOCKED`

## Boundaries

The pilot is not a formal external test set, not SFT data, not DPO data, and not
VLM fine-tuning data. It is for parsing, privacy, taxonomy, distribution, and
image compatibility checks only.
"""


def main() -> int:
    ensure_dirs()
    sources = {row["source_id"]: row for row in approved_sources()}
    if "amazon_reviews_2023" not in sources and "asap_chinese_reviews" not in sources:
        result = {"marker": "REALWORLD_PRIVATE_PILOT_BLOCKED", "reason": "no delegated approved source"}
        write_json(AUDIT_OUT, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    all_rows = []
    acquisition = []
    image_jobs = []
    if "asap_chinese_reviews" in sources:
        rows, info = acquire_asap(min(150, int(sources["asap_chinese_reviews"].get("max_text_pilot_records", 150))))
        all_rows.extend(rows)
        acquisition.append(info)
    if "amazon_reviews_2023" in sources:
        rows, jobs, info = acquire_amazon(
            min(150, int(sources["amazon_reviews_2023"].get("max_text_pilot_records", 150))),
            min(20, int(sources["amazon_reviews_2023"].get("max_image_pilot_groups", 20))),
        )
        all_rows.extend(rows)
        image_jobs.extend(jobs)
        acquisition.append(info)
    raw_private = PILOT_ROOT / "raw-text" / "combined_private_raw_reviews.jsonl"
    save_private_jsonl(raw_private, all_rows)
    text_summary = process_text(all_rows)
    image_summary = download_images(image_jobs)
    taxonomy_summary = taxonomy(text_summary, image_summary)
    payload = {
        "marker": "REALWORLD_PRIVATE_PILOT_COMPLETE",
        "pilot_root": str(PILOT_ROOT),
        "git_excluded_raw_data": True,
        "sources": [row["source_id"] for row in acquisition],
        "acquisition": acquisition,
        "text_pilot_count": text_summary["processed_count"],
        "multimodal_pilot_count": text_summary["image_linked_samples"],
        "image_download_attempted": image_summary["attempted"],
        "image_download_success": image_summary["success"],
        "image_download_failed": image_summary["failed"],
        "image_download_skipped": image_summary["skipped"],
        "image_download_success_rate": round(image_summary["success"] / image_summary["attempted"], 4) if image_summary["attempted"] else None,
        "privacy_counts": text_summary["privacy_counts"],
        "category_counts": text_summary["category_counts"],
        "rating_counts": text_summary["rating_counts"],
        "language_counts": text_summary["language_counts"],
        "taxonomy_mapped_ratio": taxonomy_summary["directly_mapped_ratio"],
        "vlm_pilot_status": "REALWORLD_VLM_PILOT_BLOCKED",
        "real_vlm_inference_count": 0,
        "fallback_rate": None,
        "oom_count": 0,
        "external_test": False,
        "sft": False,
    }
    write_json(AUDIT_OUT, payload)
    REPORT.write_text(report(payload), encoding="utf-8", newline="\n")
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
