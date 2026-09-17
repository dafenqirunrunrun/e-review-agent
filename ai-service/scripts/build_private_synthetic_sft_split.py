import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_OUT = ROOT.parent / "data-private/synthetic-sft-v1633"
MANIFEST = ROOT / "data/private_research/audit/synthetic_sft_split_manifest.json"
STATS = ROOT / "data/private_research/audit/synthetic_sft_split_statistics.json"
DOC = ROOT / "docs/182_v1632_synthetic_sft_split.md"

SOURCES = [
    ROOT / "data/rag/cases/risk_cases_240.jsonl",
    ROOT / "data/eval/review_schema_eval.jsonl",
    ROOT / "data/synthetic/golden_queries/golden_queries_strict_80.jsonl",
]

SYSTEM_PROMPT = (
    "You are an ecommerce review governance assistant. Output valid JSON only. "
    "Do not output markdown or hidden reasoning. Do not execute refunds, bans, or compensation. "
    "When evidence is insufficient, route to human review."
)


def read_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            yield json.loads(line)


def stable_hash(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_rows():
    for path in SOURCES:
        for idx, row in enumerate(read_jsonl(path)):
            yield path, idx, row


def normalize(path: Path, idx: int, row: dict) -> dict:
    if "scenario" in row and "risk_type" in row:
        review_text = str(row.get("scenario") or row.get("title") or "")
        risk_type = row.get("risk_type", "normal_review")
        risk_level = row.get("risk_level", "low")
        category = row.get("product_category", "unknown")
        evidence = row.get("evidence") or []
        scenario_family = risk_type
        template_family = str(row.get("case_id", "case")).rsplit("-", 1)[0]
    elif "comment_text" in row:
        review_text = str(row.get("comment_text") or "")
        risk_type = row.get("expected_risk_type", "normal_review")
        risk_level = row.get("expected_risk_level", "low")
        category = row.get("scenario", "schema_eval")
        evidence = row.get("expected_evidence_keywords") or []
        scenario_family = str(row.get("scenario", "schema_eval"))
        template_family = str(row.get("case_id", "schema")).rsplit("-", 1)[0]
    else:
        inp = row.get("input") or {}
        labels = row.get("evaluation_labels") or {}
        review_text = str(inp.get("query_text") or "")
        risk_type = labels.get("risk_type", "normal_review")
        risk_level = labels.get("risk_level", "low")
        category = inp.get("product_category", "unknown")
        evidence = labels.get("relevant_case_ids") or []
        scenario_family = labels.get("source_scenario", "strict_query")
        template_family = str(row.get("sample_id", "strict")).rsplit("-", 1)[0]

    need_human = risk_level in {"medium", "high"}
    assistant = {
        "risk_type": risk_type,
        "risk_level": risk_level,
        "text_evidence": [str(item)[:80] for item in evidence[:3]] or ["synthetic evidence unavailable"],
        "retrieved_case_evidence": [],
        "need_human_review": need_human,
        "route_reason": "synthetic engineering SFT target for review governance routing",
        "missing_information": [] if evidence else ["insufficient explicit evidence"],
        "unsupported_claims": [],
    }
    user = {
        "synthetic_review_text": review_text,
        "synthetic_rating": row.get("rating") or (row.get("input") or {}).get("rating"),
        "synthetic_product_category": category,
        "synthetic_retrieved_case_summary": "project-owned synthetic case metadata only",
    }
    source_name = str(path.relative_to(ROOT)).replace("\\", "/")
    group = {
        "template_family": template_family,
        "scenario_family": scenario_family,
        "paraphrase_family": str(row.get("paraphrase_family", "p0")),
        "generation_batch": str(row.get("generation_batch", source_name)),
        "source_prompt_version": str(row.get("source_prompt_version", "v1633")),
        "risk_type": risk_type,
    }
    sample = {
        "system": SYSTEM_PROMPT,
        "user": json.dumps(user, ensure_ascii=False, sort_keys=True),
        "assistant": json.dumps(assistant, ensure_ascii=False, sort_keys=True),
        "metadata": {
            "source_type": "synthetic_project_owned",
            "source_name": source_name,
            "source_index": idx,
            "risk_type": risk_type,
            "risk_level": risk_level,
            "group": group,
        },
    }
    sample_hash = stable_hash(sample)
    group_hash = stable_hash(group)
    sample["metadata"]["sample_hash"] = sample_hash
    sample["metadata"]["group_hash"] = group_hash
    return sample


def assign_splits(samples: list[dict]) -> None:
    groups = defaultdict(list)
    for sample in samples:
        groups[sample["metadata"]["group_hash"]].append(sample)
    ordered = sorted(groups.items(), key=lambda item: item[0])
    total = len(samples)
    targets = {"train": int(total * 0.8), "validation": int(total * 0.1)}
    counts = Counter()
    for _, group_samples in ordered:
        if counts["train"] + len(group_samples) <= targets["train"]:
            split = "train"
        elif counts["validation"] + len(group_samples) <= targets["validation"]:
            split = "validation"
        else:
            split = "engineering_holdout"
        for sample in group_samples:
            sample["metadata"]["split"] = split
        counts[split] += len(group_samples)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def main():
    samples = [normalize(path, idx, row) for path, idx, row in source_rows()]
    assign_splits(samples)
    PRIVATE_OUT.mkdir(parents=True, exist_ok=True)
    for split in ["train", "validation", "engineering_holdout"]:
        write_jsonl(PRIVATE_OUT / f"{split}.jsonl", [sample for sample in samples if sample["metadata"]["split"] == split])

    split_counts = Counter(sample["metadata"]["split"] for sample in samples)
    group_to_split = {}
    leakage = 0
    for sample in samples:
        group_hash = sample["metadata"]["group_hash"]
        split = sample["metadata"]["split"]
        if group_hash in group_to_split and group_to_split[group_hash] != split:
            leakage += 1
        group_to_split[group_hash] = split
    manifest_rows = [
        {
            "sample_hash": sample["metadata"]["sample_hash"],
            "group_hash": sample["metadata"]["group_hash"],
            "split": sample["metadata"]["split"],
            "risk_type": sample["metadata"]["risk_type"],
            "risk_level": sample["metadata"]["risk_level"],
            "source_name": sample["metadata"]["source_name"],
        }
        for sample in samples
    ]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"rows": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = {
        "status": "PRIVATE_SYNTHETIC_SFT_SPLIT_PASS" if leakage == 0 else "PRIVATE_SYNTHETIC_SFT_SPLIT_BLOCKED",
        "source_type": "synthetic_project_owned",
        "total_count": len(samples),
        "split_counts": dict(split_counts),
        "group_count": len(group_to_split),
        "cross_split_group_leakage_count": leakage,
        "risk_type_distribution": dict(Counter(sample["metadata"]["risk_type"] for sample in samples)),
        "risk_level_distribution": dict(Counter(sample["metadata"]["risk_level"] for sample in samples)),
        "private_output_label": "<data-private>/synthetic-sft-v1633",
    }
    STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.3.3 Synthetic SFT Split\n\n"
        f"Status: `{stats['status']}`\n\n"
        f"- total_count: `{stats['total_count']}`\n"
        f"- split_counts: `{stats['split_counts']}`\n"
        f"- cross_split_group_leakage_count: `{leakage}`\n"
        "\nFull training records are stored outside Git; Git stores only hashes and aggregate statistics.\n",
        encoding="utf-8",
    )
    print(stats["status"])


if __name__ == "__main__":
    main()
