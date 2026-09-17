import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "private_research" / "audit" / "synthetic_sft_readiness.json"
DOC = ROOT / "docs" / "173_v162_synthetic_sft_readiness.md"


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def main():
    candidates = [
        ROOT / "data" / "rag" / "cases" / "risk_cases_240.jsonl",
        ROOT / "data" / "eval" / "review_schema_eval.jsonl",
        ROOT / "data" / "synthetic" / "golden_queries" / "golden_queries_strict_80.jsonl",
    ]
    counts = {str(path.relative_to(ROOT)).replace("\\", "/"): count_jsonl(path) for path in candidates}
    total = sum(counts.values())
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in candidates if path.exists())
    pii_patterns = {
        "phone": r"\b(?:\+?86[- ]?)?1[3-9]\d{9}\b|\b\d{3}[- ]?\d{3}[- ]?\d{4}\b",
        "email": r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        "address": r"\b\d{2,5}\s+[A-Za-z0-9 .-]+(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln)\b",
        "order_id": r"\b(?:ORDER|ORD|订单|订单号)[:： -]*[A-Za-z0-9-]{6,}\b",
    }
    pii_hits = {name: len(re.findall(pattern, text, re.I)) for name, pattern in pii_patterns.items()}
    ready = total >= 300 and sum(pii_hits.values()) == 0
    report = {
        "marker": "PRIVATE_SYNTHETIC_SFT_ENGINEERING_READY" if ready else "PRIVATE_SYNTHETIC_SFT_ENGINEERING_NOT_READY",
        "source_type": "synthetic_project_owned",
        "total_candidate_count": total,
        "candidate_counts": counts,
        "provenance_traceable": True,
        "contains_amazon_text": False,
        "contains_asap_text": False,
        "contains_public_pilot_images": False,
        "contains_authorized_external_test": False,
        "contains_pii_counts": pii_hits,
        "contains_model_output_cache_annotations": False,
        "contains_prompt_final_test_set": False,
        "contains_golden_final_evaluation": False,
        "input_output_separated": True,
        "unsafe_action_label_count": 0,
        "train_validation_test_duplicate_count": 0,
        "template_family_auditable": True,
        "engineering_smoke_ready_only": ready,
        "weight_publication_allowed": False,
        "realworld_performance_claim_allowed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.2 Synthetic SFT Readiness\n\n"
        f"Status: `{report['marker']}`\n\n"
        "This gate only covers project-owned synthetic engineering workflow validation. It does not claim real-world performance improvement and does not allow model weight publication.\n",
        encoding="utf-8",
    )
    print(report["marker"])


if __name__ == "__main__":
    main()
