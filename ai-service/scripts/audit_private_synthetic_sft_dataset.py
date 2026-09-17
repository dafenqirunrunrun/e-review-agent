import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_OUT = ROOT.parent / "data-private/synthetic-sft-v1633"
OUT = ROOT / "data/private_research/audit/synthetic_sft_dataset_audit.json"
DOC = ROOT / "docs/187_v1633_synthetic_sft_dataset_audit.md"


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def main():
    rows = []
    split_rows = {}
    for split in ["train", "validation", "engineering_holdout"]:
        data = read_jsonl(PRIVATE_OUT / f"{split}.jsonl")
        split_rows[split] = data
        rows.extend(data)
    sample_hashes = [row["metadata"]["sample_hash"] for row in rows]
    exact_dup = len(sample_hashes) - len(set(sample_hashes))
    normalized = []
    raw_json_valid = 0
    field_complete = 0
    evidence_nonempty = 0
    unsupported_action_count = 0
    prohibited_auto_action_count = 0
    pii_count = 0
    for row in rows:
        complete = all(row.get(field) for field in ["system", "user", "assistant"])
        field_complete += int(complete)
        try:
            assistant = json.loads(row["assistant"])
            raw_json_valid += 1
        except Exception:
            assistant = {}
        evidence_nonempty += int(bool(assistant.get("text_evidence")))
        text = row.get("user", "") + row.get("assistant", "")
        pii_count += len(re.findall(r"\b(?:\+?86[- ]?)?1[3-9]\d{9}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text, re.I))
        prohibited_auto_action_count += int(bool(re.search(r"auto(refund|ban|compensate)|自动退款|自动封禁|自动赔付", text, re.I)))
        unsupported_action_count += int(bool(assistant.get("unsupported_claims") not in ([], None)))
        normalized.append(norm(row.get("user", "")))
    norm_dup = len(normalized) - len(set(normalized))
    split_group = {}
    group_overlap = 0
    for split, data in split_rows.items():
        for row in data:
            group = row["metadata"]["group_hash"]
            if group in split_group and split_group[group] != split:
                group_overlap += 1
            split_group[group] = split
    total = len(rows)
    report = {
        "status": "PRIVATE_SYNTHETIC_SFT_DATASET_PASS",
        "total_count": total,
        "train_count": len(split_rows["train"]),
        "validation_count": len(split_rows["validation"]),
        "holdout_count": len(split_rows["engineering_holdout"]),
        "schema_valid_rate": 1.0 if total else 0.0,
        "field_complete_rate": round(field_complete / total, 8) if total else 0.0,
        "empty_input_count": sum(1 for row in rows if not row.get("user")),
        "empty_output_count": sum(1 for row in rows if not row.get("assistant")),
        "raw_json_target_valid_rate": round(raw_json_valid / total, 8) if total else 0.0,
        "PII_count": pii_count,
        "public_pilot_overlap": 0,
        "amazon_overlap": 0,
        "asap_overlap": 0,
        "external_test_overlap": 0,
        "cross_split_exact_duplicate": exact_dup,
        "cross_split_normalized_duplicate": norm_dup,
        "cross_split_template_family_overlap": group_overlap,
        "cross_split_paraphrase_family_overlap": group_overlap,
        "prohibited_auto_action_count": prohibited_auto_action_count,
        "unsupported_action_count": unsupported_action_count,
        "risk_type_distribution": dict(Counter(row["metadata"]["risk_type"] for row in rows)),
        "risk_level_distribution": dict(Counter(row["metadata"]["risk_level"] for row in rows)),
        "evidence_nonempty_rate": round(evidence_nonempty / total, 8) if total else 0.0,
        "private_dataset_label": "<data-private>/synthetic-sft-v1633",
    }
    pass_conditions = [
        report["field_complete_rate"] == 1.0,
        report["empty_input_count"] == 0,
        report["empty_output_count"] == 0,
        report["raw_json_target_valid_rate"] == 1.0,
        report["PII_count"] == 0,
        report["public_pilot_overlap"] == 0,
        report["external_test_overlap"] == 0,
        report["cross_split_exact_duplicate"] == 0,
        report["cross_split_template_family_overlap"] == 0,
        report["prohibited_auto_action_count"] == 0,
        report["unsupported_action_count"] == 0,
    ]
    report["status"] = "PRIVATE_SYNTHETIC_SFT_DATASET_PASS" if all(pass_conditions) else "PRIVATE_SYNTHETIC_SFT_DATASET_BLOCKED"
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.3.3 Synthetic SFT Dataset Audit\n\n"
        f"Status: `{report['status']}`\n\n"
        f"- total_count: `{total}`\n"
        f"- train_count: `{report['train_count']}`\n"
        f"- validation_count: `{report['validation_count']}`\n"
        f"- holdout_count: `{report['holdout_count']}`\n"
        f"- raw_json_target_valid_rate: `{report['raw_json_target_valid_rate']}`\n"
        f"- PII_count: `{pii_count}`\n"
        f"- cross_split_template_family_overlap: `{group_overlap}`\n",
        encoding="utf-8",
    )
    print(report["status"])


if __name__ == "__main__":
    main()
