import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PATTERNS = {
    "PHONE": re.compile(r"\b(?:\+?86[- ]?)?1[3-9]\d{9}\b|\b\d{3}[- ]?\d{3}[- ]?\d{4}\b"),
    "EMAIL": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "ORDER_ID": re.compile(r"\b(?:ORDER|ORD|订单|订单号)[:： -]*[A-Za-z0-9-]{6,}\b", re.I),
    "TRACKING_ID": re.compile(r"\b(?:TRACK|快递|运单|tracking)[:： -]*[A-Za-z0-9-]{6,}\b", re.I),
    "ACCOUNT": re.compile(r"\b(?:account|账号|ID)[:： -]*[A-Za-z0-9_.-]{4,}\b", re.I),
    "URL": re.compile(r"https?://[^\s?]+(?:\?[^\s]+)?"),
    "ADDRESS": re.compile(r"\b\d{2,5}\s+[A-Za-z0-9 .-]+(?:Road|Rd|Street|St|Avenue|Ave|Lane|Ln)\b", re.I),
}


def redact_text(text: str):
    counts = {}
    result = text
    for label, pattern in PATTERNS.items():
        result, count = pattern.subn(f"[{label}]", result)
        counts[label] = count
    return result, counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=False)
    parser.add_argument("--out", default="data/authorized_intake/statistics/redaction_summary.json")
    args = parser.parse_args()
    total = 0
    counts = {name: 0 for name in PATTERNS}
    if args.input and Path(args.input).exists():
        for line in Path(args.input).read_text(encoding="utf-8", errors="replace").splitlines():
            redacted, line_counts = redact_text(line)
            total += 1
            for key, value in line_counts.items():
                counts[key] += value
    summary = {
        "marker": "AUTHORIZED_TEXT_REDACTION_SUMMARY",
        "records_processed": total,
        "replacement_counts": counts,
        "raw_text_written_to_git": False,
        "llm_rewrite_used": False,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(summary["marker"])


if __name__ == "__main__":
    main()
