import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag_v2.corpus_loader import load_jsonl


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "115_v161_sft_data_readiness_report.md"
AUDIT_PATH = ROOT / "data" / "multimodal" / "audit" / "sft_data_readiness.json"


def exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def safe_load(path: Path) -> List[Dict]:
    return load_jsonl(path) if exists(path) else []


def contains_privacy(text: str) -> bool:
    patterns = [
        r"1[3-9]\d{9}",
        r"\d{6,}",
        r"(address|phone|mobile|tracking|express|order)[\s:：#-]*\S+",
        r"(地址|手机号|电话|快递单|订单号)[\s:：#-]*\S+",
    ]
    return any(re.search(pattern, text or "", flags=re.IGNORECASE) for pattern in patterns)


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def report_text(result: Dict) -> str:
    reasons = "\n".join(f"- {item}" for item in result["blocking_reasons"])
    checks = "\n".join(f"| {key} | {value} |" for key, value in result["checks"].items())
    return f"""# v1.6.1 SFT Data Readiness Audit Report

## Conclusion

- Text SFT: `{result['sft_status']}`
- VLM SFT: `{result['vlm_sft_status']}`

## Blocking Reasons

{reasons}

## Checks

| Check | Result |
| --- | --- |
{checks}

## Notes

This stage does not run QLoRA-SFT, DPO, or VLM fine-tuning. The current v1.6 synthetic data remains suitable for regression coverage and long-tail scenario checks, but real external text data, real multimodal data, dual-annotator agreement, privacy filtering, and license readiness are not complete. Therefore the project must not enter SFT.
"""


def main() -> int:
    synthetic_reviews = safe_load(ROOT / "data/rag/comments/review_samples_1200.jsonl")
    strict_queries = safe_load(ROOT / "data/synthetic/golden_queries/golden_queries_strict_80.jsonl")
    real_dev = safe_load(ROOT / "data/real_world/processed/real_reviews_dev_400.jsonl")
    real_external = safe_load(ROOT / "data/real_world/external_test/real_reviews_external_test_200.jsonl")
    multimodal_external = safe_load(ROOT / "data/real_world/multimodal_manifest/real_multimodal_external_test.jsonl")
    source_manifest = safe_load(ROOT / "data/real_world/source_manifest/source_manifest.jsonl")

    risk_counts = Counter(row.get("risk_type") for row in synthetic_reviews)
    privacy_hits = [
        row.get("review_id", row.get("sample_id", "unknown"))
        for row in synthetic_reviews
        if contains_privacy(row.get("review_text", ""))
    ]
    blocking = []
    if len(real_dev) < 400:
        blocking.append(f"real_world dev requires at least 400 text samples; current={len(real_dev)}")
    if len(real_external) < 200:
        blocking.append(f"real_world external test requires at least 200 text samples; current={len(real_external)}")
    if len(multimodal_external) < 40:
        blocking.append(
            f"real multimodal external test requires at least 40 image-text samples; current={len(multimodal_external)}"
        )
    if not any(row.get("status") == "candidate_allowed_for_research_after_privacy_filtering" for row in source_manifest):
        blocking.append("no source manifest entry is currently allowed for research after privacy filtering")
    if not strict_queries:
        blocking.append("strict synthetic query set is missing")
    if privacy_hits:
        blocking.append(f"training candidate text contains privacy-like fields: count={len(privacy_hits)}")

    checks = {
        "synthetic_review_count": len(synthetic_reviews),
        "strict_query_count": len(strict_queries),
        "real_dev_count": len(real_dev),
        "real_external_count": len(real_external),
        "multimodal_external_count": len(multimodal_external),
        "source_manifest_count": len(source_manifest),
        "synthetic_risk_type_distribution": dict(risk_counts),
        "privacy_hit_count": len(privacy_hits),
        "independent_final_test_available": len(real_external) >= 200 and len(multimodal_external) >= 40,
    }
    result = {
        "sft_status": "SFT_DATA_READY" if not blocking else "SFT_DATA_NOT_READY",
        "vlm_sft_status": "VLM_SFT_DATA_READY" if len(multimodal_external) >= 200 and not blocking else "VLM_SFT_DATA_NOT_READY",
        "blocking_reasons": blocking,
        "checks": checks,
    }
    write_json(AUDIT_PATH, result)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["sft_status"])
    print(result["vlm_sft_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
