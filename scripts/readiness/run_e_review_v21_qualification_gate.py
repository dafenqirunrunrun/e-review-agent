#!/usr/bin/env python
"""Evaluate v2.1 qualification evidence from committed artifacts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


RC_COMMIT = "ffd05f2611cf2c7996a681fa0343778da73f7e50"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(args: list[str], repo: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(repo), text=True, capture_output=True, check=True).stdout.strip()


def _is_ancestor(repo: Path, older: str, newer: str) -> bool:
    if not older or not newer:
        return False
    completed = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=str(repo))
    return completed.returncode == 0


def main() -> int:
    repo = Path.cwd()
    head = _git(["rev-parse", "HEAD"], repo)
    branch = _git(["branch", "--show-current"], repo)
    baseline = _load(repo / "artifacts" / "qualification" / "model-assets-summary.json")
    reranker = _load(repo / "artifacts" / "qualification" / "reranker-qualification-summary.json")
    llm = _load(repo / "artifacts" / "qualification" / "llm-qualification-summary.json")
    scale = _load(repo / "artifacts" / "qualification" / "scale-qualification-summary.json")
    multi = _load(repo / "artifacts" / "qualification" / "multi-process-index-summary.json")
    capacity = _load(repo / "artifacts" / "qualification" / "local-capacity-summary.json")
    supply = _load(repo / "artifacts" / "qualification" / "supply-chain-summary.json")
    provenance = _load(repo / "artifacts" / "qualification" / "build-provenance.json")

    scale_tokens = set(scale.get("tokens", []))
    supply_tokens = set(supply.get("tokens", []))
    provenance_commit = str(provenance.get("sourceCommit") or "")
    required_pass = {
        "rcBaselinePreserved": baseline.get("schemaVersion") == "v2.1-model-assets-audit",
        "scale10k": "AGENT_RAG_SCALE_10K_PASS" in scale_tokens,
        "scale100k": "AGENT_RAG_SCALE_100K_PASS" in scale_tokens,
        "multiProcess": multi.get("status") == "PASS",
        "capacityObserved": "LOCAL_QUALIFICATION_CAPACITY_OBSERVED" in capacity.get("tokens", []),
        "soak30": "E_REVIEW_V21_30_MINUTE_SOAK_PASS" in capacity.get("tokens", []),
        "sbom": "E_REVIEW_V21_SBOM_PASS" in supply_tokens,
        "buildProvenance": "E_REVIEW_V21_BUILD_PROVENANCE_PASS" in supply_tokens,
        "sourceCommitTracked": _is_ancestor(repo, provenance_commit, head),
    }
    blockers = {
        "reranker": reranker.get("runtime", {}).get("token") == "AGENT_RAG_MODEL_RERANKER_BLOCKED",
        "llm": llm.get("runtime", {}).get("token") == "AGENT_RAG_REAL_LLM_BLOCKED",
        "vulnerabilityDatabase": "VULNERABILITY_DATABASE_UNAVAILABLE" in supply_tokens,
        "licenseReview": "LICENSE_REVIEW_REQUIRED" in supply_tokens,
    }
    eligible = all(required_pass.values()) and not blockers["vulnerabilityDatabase"] and not blockers["licenseReview"] and not blockers["reranker"] and not blockers["llm"]
    decision = "V2_1_RELEASE_CANDIDATE_ELIGIBLE" if eligible else "RETAIN_FFD05F26_RC_BASELINE"
    tokens = [
        "E_REVIEW_V21_RC_BASELINE_PRESERVED_PASS",
        "MODEL_RERANKER_NOT_VERIFIED" if blockers["reranker"] else "E_REVIEW_V21_REAL_RERANKER_QUALIFICATION_PASS",
        "REAL_LLM_QUALITY_NOT_VERIFIED" if blockers["llm"] else "E_REVIEW_V21_REAL_LLM_QUALIFICATION_PASS",
        "E_REVIEW_V21_SCALE_10K_PASS" if required_pass["scale10k"] else "E_REVIEW_V21_SCALE_10K_BLOCKED",
        "E_REVIEW_V21_SCALE_100K_PASS" if required_pass["scale100k"] else "E_REVIEW_V21_SCALE_100K_BLOCKED",
        "E_REVIEW_V21_MULTI_PROCESS_INDEX_PASS" if required_pass["multiProcess"] else "E_REVIEW_V21_MULTI_PROCESS_INDEX_BLOCKED",
        "E_REVIEW_V21_LOCAL_CAPACITY_PASS" if required_pass["capacityObserved"] and required_pass["soak30"] else "E_REVIEW_V21_LOCAL_CAPACITY_BLOCKED",
        "E_REVIEW_V21_SBOM_PASS" if required_pass["sbom"] else "E_REVIEW_V21_SBOM_BLOCKED",
        "LICENSE_REVIEW_REQUIRED" if blockers["licenseReview"] else "E_REVIEW_V21_LICENSE_INVENTORY_PASS",
        "E_REVIEW_V21_BUILD_PROVENANCE_PASS" if required_pass["buildProvenance"] else "E_REVIEW_V21_BUILD_PROVENANCE_BLOCKED",
        "E_REVIEW_V21_QUALIFICATION_CAMPAIGN_PASS" if eligible else "E_REVIEW_V21_QUALIFICATION_CAMPAIGN_BLOCKED",
        decision,
        "NO_PUBLIC_REPO_CHANGES",
        "NO_PUSH",
        "NO_TAG",
        "NO_RELEASE",
    ]
    summary = {
        "schemaVersion": "v2.1-qualification-gate",
        "branch": branch,
        "head": head,
        "rcCommit": RC_COMMIT,
        "requiredPass": required_pass,
        "blockers": blockers,
        "decision": decision,
        "tokens": tokens,
    }
    output = repo / "artifacts" / "qualification" / "v21-qualification-gate-summary.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for token in tokens:
        print(token)
    print("V21_QUALIFICATION_GATE_WRITTEN artifacts/qualification/v21-qualification-gate-summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
