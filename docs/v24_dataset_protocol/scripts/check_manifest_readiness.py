from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
validation = json.loads((BASE / "dataset_protocol_validation.json").read_text(encoding="utf-8-sig"))
history = json.loads((BASE / "inventory" / "historical_dataset_inventory.json").read_text(encoding="utf-8-sig"))
issues = json.loads((BASE / "review" / "REVIEW_ISSUES.json").read_text(encoding="utf-8-sig"))
errors = []
if validation["classification"] != "PASS_WITH_WARNINGS":
    errors.append("classification must be PASS_WITH_WARNINGS")
if validation["datasetCollectionStarted"] is not False or validation["formalSamplesCreated"] != 0:
    errors.append("protocol package must not create formal samples")
if history["summary"]["formalReusableForNewEvaluation"] != 0:
    errors.append("historical assets must not be reusable as new final evaluation")
if issues["summary"]["p0Open"] != 0 or issues["summary"]["p1Open"] != 0:
    errors.append("P0/P1 must be zero")
if validation["readiness"]["readyForPilot60Collection"] is not True:
    errors.append("Pilot 60 readiness should be true")
if validation["readiness"]["readyForFormal500Collection"] or validation["readiness"]["readyForEvaluation"]:
    errors.append("Formal/evaluation readiness must remain false")
if errors:
    for err in errors:
        print("[FAIL]", err)
    raise SystemExit(1)
print("[PASS] Dataset protocol manifest readiness is consistent")
