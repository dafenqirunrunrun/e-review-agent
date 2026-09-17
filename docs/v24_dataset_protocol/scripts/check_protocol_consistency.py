from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
required_docs = [
    "00_RESEARCH_SYNTHESIS.md", "01_DATASET_OBJECTIVES.md", "02_CURRENT_PROJECT_DATA_INVENTORY.md",
    "03_RISK_ONTOLOGY.md", "04_SOURCE_AND_COMPLIANCE_POLICY.md", "05_SCREENING_PROTOCOL.md",
    "06_DEDUPLICATION_PROTOCOL.md", "07_ANNOTATION_GUIDELINES.md", "08_EVIDENCE_AND_CITATION_LABELING.md",
    "09_SPLIT_AND_LEAKAGE_POLICY.md", "10_QUALITY_ASSURANCE_AND_ADJUDICATION.md", "11_PILOT_60_DESIGN.md",
    "12_DATASET_VERSIONING_AND_MANIFEST.md", "13_DATASET_COLLECTION_RUNBOOK.md", "14_PROTOCOL_DECISION_LOG.md",
    "15_PROTOCOL_REVIEW_REPORT.md", "16_PILOT_READINESS.md", "17_EXECUTIVE_SUMMARY.md",
]
errors: list[str] = []
for name in required_docs:
    if not (BASE / name).is_file():
        errors.append(f"Missing document: {name}")

ontology = json.loads((BASE / "schema" / "risk_ontology_v0.1.json").read_text(encoding="utf-8-sig"))
codes = [x["code"] for x in ontology["codes"]]
if len(codes) != len(set(codes)):
    errors.append("Risk ontology contains duplicate codes")

validation = json.loads((BASE / "dataset_protocol_validation.json").read_text(encoding="utf-8-sig"))
if validation.get("protocolVersion") != "dataset-protocol-v0.1":
    errors.append("protocolVersion must be dataset-protocol-v0.1")
if validation.get("datasetCollectionStarted") is not False:
    errors.append("Dataset collection must remain false in protocol package")
if validation.get("formalSamplesCreated") != 0:
    errors.append("Formal samples must remain zero")
review = validation.get("review", {})
if review.get("p0Open") != 0 or review.get("p1Open") != 0:
    errors.append("P0/P1 must be closed before v0.1 sealing")
if review.get("adversarialCasesReviewed", 0) < 20:
    errors.append("At least 20 adversarial cases must be reviewed")
ready = validation.get("readiness", {})
if ready.get("readyForPilot60Collection") is not True:
    errors.append("Pilot 60 readiness must be true after adaptation")
if ready.get("readyForFormal500Collection") is not False:
    errors.append("Formal 500 readiness must remain false")
if ready.get("readyForEvaluation") is not False:
    errors.append("Evaluation readiness must remain false")

texts = "\n".join((BASE / name).read_text(encoding="utf-8-sig") for name in required_docs)
for term in ["dataset-protocol-v0.1", "READY_FOR_PILOT_60_COLLECTION=true", "READY_FOR_FORMAL_500_COLLECTION=false"]:
    if term not in texts:
        errors.append(f"Missing consistency term: {term}")

if errors:
    for err in errors:
        print(f"[FAIL] {err}")
    raise SystemExit(1)
print(f"[PASS] {len(required_docs)} required documents found")
print(f"[PASS] {len(codes)} unique audited risk codes")
print("[PASS] P0/P1 closed and readiness boundaries are consistent")
