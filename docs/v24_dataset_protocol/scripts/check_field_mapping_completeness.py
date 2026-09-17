from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
mapping = json.loads((BASE / "inventory" / "project_field_mapping.json").read_text(encoding="utf-8-sig"))
required = {"primaryRiskType", "secondaryRiskTypes", "severity", "answerable", "requiresHumanReview", "goldEvidenceIds", "sourceType", "sampleId"}
seen = {row.get("datasetField") for row in mapping.get("fieldMappings", [])}
errors = []
missing = sorted(required - seen)
if missing:
    errors.append(f"Missing mappings: {missing}")
if not mapping.get("singleSourceContracts"):
    errors.append("singleSourceContracts is empty")
for row in mapping.get("fieldMappings", []):
    if not row.get("runtimeField") or not row.get("status"):
        errors.append(f"Incomplete mapping row: {row}")
if errors:
    for err in errors:
        print("[FAIL]", err)
    raise SystemExit(1)
print(f"[PASS] {len(seen)} project field mappings are complete")
