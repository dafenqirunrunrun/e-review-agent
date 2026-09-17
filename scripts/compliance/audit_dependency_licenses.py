from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "compliance" / "license-policy.yml"
INPUT = ROOT / "artifacts" / "qualification" / "dependency-license-inventory.json"
OUT = ROOT / "artifacts" / "qualification" / "license-review-summary.json"


def _read_policy() -> dict[str, set[str] | str]:
    text = POLICY.read_text(encoding="utf-8")
    sections: dict[str, set[str] | str] = {"allowed": set(), "review_required": set(), "denied": set(), "unknown_action": "review"}
    current: str | None = None
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_]+:", line):
            key, _, value = line.partition(":")
            current = key.strip()
            if value.strip():
                sections[current] = value.strip()
            elif current not in sections:
                sections[current] = set()
            continue
        if current and line.lstrip().startswith("-"):
            value = line.split("-", 1)[1].strip()
            bucket = sections.setdefault(current, set())
            if isinstance(bucket, set):
                bucket.add(value)
    return sections


def _decision(license_name: str, policy: dict[str, set[str] | str]) -> str:
    normalized = (license_name or "UNKNOWN").strip() or "UNKNOWN"
    if normalized in policy.get("denied", set()):
        return "DENIED"
    if normalized in policy.get("allowed", set()):
        return "ALLOWED"
    if normalized in policy.get("review_required", set()) or normalized.upper() == "UNKNOWN":
        return "REVIEW_REQUIRED"
    return "REVIEW_REQUIRED"


def main() -> int:
    policy = _read_policy()
    inventory = json.loads(INPUT.read_text(encoding="utf-8")) if INPUT.exists() else {"components": []}
    rows: list[dict[str, Any]] = []
    counts = {"ALLOWED": 0, "REVIEW_REQUIRED": 0, "DENIED": 0}
    for component in inventory.get("components", []):
        license_name = component.get("license") or component.get("detectedLicense") or "UNKNOWN"
        decision = _decision(license_name, policy)
        counts[decision] += 1
        rows.append(
            {
                "ecosystem": component.get("ecosystem"),
                "name": component.get("name"),
                "version": component.get("version"),
                "detectedLicense": license_name,
                "evidenceSource": component.get("evidenceSource", "existing-inventory"),
                "policyDecision": decision,
            }
        )
    payload = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceInventory": "artifacts/qualification/dependency-license-inventory.json",
        "policy": "compliance/license-policy.yml",
        "totalPackages": len(rows),
        "allowed": counts["ALLOWED"],
        "reviewRequired": counts["REVIEW_REQUIRED"],
        "denied": counts["DENIED"],
        "unknown": sum(1 for row in rows if str(row["detectedLicense"]).upper() == "UNKNOWN"),
        "status": "LICENSE_REVIEW_REQUIRED" if counts["REVIEW_REQUIRED"] or counts["DENIED"] else "PASS",
        "components": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if counts["DENIED"]:
        print("E_REVIEW_LICENSE_AUDIT_DENIED_DEPENDENCY_FOUND")
        return 1
    if counts["REVIEW_REQUIRED"]:
        print("LICENSE_REVIEW_REQUIRED")
    else:
        print("E_REVIEW_V21_LICENSE_AUDIT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
