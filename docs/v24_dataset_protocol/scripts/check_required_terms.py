from __future__ import annotations
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
checks = {
    "04_SOURCE_AND_COMPLIANCE_POLICY.md": ["rawText", "redactedText", "normalizedText", "PII"],
    "06_DEDUPLICATION_PROTOCOL.md": ["SHA-256", "Jaccard", "BGE-M3", "duplicateGroupId", "scenarioGroupId"],
    "07_ANNOTATION_GUIDELINES.md": ["answerable", "requiresHumanReview", "annotationRationale"],
    "08_EVIDENCE_AND_CITATION_LABELING.md": ["goldEvidenceIds", "Citation", "minimumSufficientEvidenceSet"],
    "09_SPLIT_AND_LEAKAGE_POLICY.md": ["seenDuringDevelopment", "Group-level Split"],
    "10_QUALITY_ASSURANCE_AND_ADJUDICATION.md": ["Cohen", "P0", "P1"],
    "15_PROTOCOL_REVIEW_REPORT.md": ["P0 Open?0", "P1 Open?0", "PASS_WITH_WARNINGS"],
    "16_PILOT_READINESS.md": ["READY_FOR_PILOT_60_COLLECTION=true", "READY_FOR_FORMAL_500_COLLECTION=false"],
}
errors: list[str] = []
for filename, terms in checks.items():
    text = (BASE / filename).read_text(encoding="utf-8-sig")
    for term in terms:
        if term not in text:
            errors.append(f"{filename}: missing required term '{term}'")
if errors:
    for err in errors:
        print("[FAIL]", err)
    raise SystemExit(1)
print("[PASS] Required protocol terms are present")
