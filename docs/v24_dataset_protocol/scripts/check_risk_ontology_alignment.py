from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ontology = json.loads((BASE / "schema" / "risk_ontology_v0.1.json").read_text(encoding="utf-8-sig"))
annotation = json.loads((BASE / "schema" / "dataset_annotation.schema.json").read_text(encoding="utf-8-sig"))
allowed_runtime = {"normal_review", "negative_review", "after_sales_risk"}
allowed_levels = {"low", "medium", "high"}
errors: list[str] = []
codes = {row["code"] for row in ontology.get("codes", [])}
primary_enum = set(annotation["properties"]["primaryRiskType"].get("enum", []))
secondary_enum = set(annotation["properties"]["secondaryRiskTypes"]["items"].get("enum", []))
if codes != primary_enum:
    errors.append(f"Primary risk enum mismatch: ontology={sorted(codes)} schema={sorted(primary_enum)}")
if codes != secondary_enum:
    errors.append("Secondary risk enum mismatch")
for row in ontology.get("codes", []):
    if row.get("runtimeRiskType") not in allowed_runtime:
        errors.append(f"{row['code']} maps to unsupported runtime risk type {row.get('runtimeRiskType')}")
    if row.get("defaultRuntimeRiskLevel") not in allowed_levels:
        errors.append(f"{row['code']} maps to unsupported risk level {row.get('defaultRuntimeRiskLevel')}")
if errors:
    for err in errors:
        print("[FAIL]", err)
    raise SystemExit(1)
print("[PASS] Risk ontology aligns with dataset annotation schema and runtime canonical values")
