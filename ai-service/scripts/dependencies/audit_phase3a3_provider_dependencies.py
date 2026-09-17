from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


TARGET_REQUIREMENTS = ("FlagEmbedding==1.3.5", "sentence-transformers==3.0.1")
IGNORED_EXTRAS = ("finetune", "dev", "train")


@dataclass(frozen=True)
class DistributionInfo:
    name: str
    version: str
    requires: tuple[str, ...] = ()


DistributionProvider = Callable[[str], DistributionInfo | None]


def installed_distribution(name: str) -> DistributionInfo | None:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return None
    return DistributionInfo(name=dist.metadata.get("Name", name), version=dist.version, requires=tuple(dist.requires or ()))


def audit_environment(
    *,
    targets: tuple[str, ...] = TARGET_REQUIREMENTS,
    distribution_provider: DistributionProvider = installed_distribution,
) -> dict[str, Any]:
    installed: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, str]] = []
    mismatches: list[dict[str, str]] = []
    satisfied: list[dict[str, str]] = []
    visited: set[str] = set()
    pending = list(targets)
    ignored_markers: list[dict[str, str]] = []

    while pending:
        requirement_text = pending.pop(0)
        requirement = Requirement(requirement_text)
        if requirement.marker and not marker_applies(requirement):
            ignored_markers.append({"requirement": requirement_text, "marker": str(requirement.marker)})
            continue

        normalized_name = canonicalize_name(requirement.name)
        if normalized_name in visited:
            continue
        visited.add(normalized_name)

        dist = distribution_provider(requirement.name)
        if dist is None:
            missing.append({"name": requirement.name, "requirement": requirement_text})
            continue

        installed[normalized_name] = {
            "name": dist.name,
            "version": dist.version,
            "requires": list(dist.requires),
        }
        if requirement.specifier and Version(dist.version) not in requirement.specifier:
            mismatches.append(
                {
                    "name": dist.name,
                    "installed": dist.version,
                    "requirement": requirement_text,
                }
            )
            continue

        satisfied.append({"name": dist.name, "version": dist.version, "requirement": requirement_text})
        for child in dist.requires:
            try:
                child_requirement = Requirement(child)
            except Exception:
                continue
            if child_requirement.marker and not marker_applies(child_requirement):
                ignored_markers.append({"requirement": child, "marker": str(child_requirement.marker)})
                continue
            pending.append(child)

    payload = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if not missing and not mismatches else "BLOCKED",
        "python": sys.version,
        "targets": list(targets),
        "installed": sorted(installed.values(), key=lambda item: canonicalize_name(item["name"])),
        "missing": missing,
        "versionMismatches": mismatches,
        "satisfied": satisfied,
        "ignoredExtras": list(IGNORED_EXTRAS),
        "ignoredMarkers": ignored_markers,
        "networkUsed": False,
        "environmentModified": False,
    }
    return payload


def marker_applies(requirement: Requirement) -> bool:
    if requirement.marker is None:
        return True
    try:
        return bool(requirement.marker.evaluate({"extra": ""}))
    except Exception:
        return True


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit optional Phase 3A.3 provider dependencies without installing packages.")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = audit_environment()
    write_json(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
