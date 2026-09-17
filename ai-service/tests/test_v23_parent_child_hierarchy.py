from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_common import (  # noqa: E402
    build_parent_units,
    hierarchy_audit_payload,
    make_parent_id,
    parent_index_manifest_payload,
)


def test_parent_id_is_deterministic() -> None:
    first = make_parent_id("tenant-a", "doc-1", "root")
    second = make_parent_id("tenant-a", "doc-1", "root")
    different = make_parent_id("tenant-a", "doc-1", "section")
    assert first == second
    assert first != different
    assert first.startswith("parent-")


def test_all_eligible_children_map_to_one_parent() -> None:
    audit = hierarchy_audit_payload()
    assert audit["childChunkCount"] == 153
    assert audit["orphanChildCount"] == 0
    assert audit["duplicateChildMappingCount"] == 0
    assert audit["crossTenantMappingCount"] == 0
    assert audit["crossDocumentMappingCount"] == 0


def test_parent_content_is_bounded_and_not_stored_in_audit() -> None:
    parents = build_parent_units()
    assert parents
    assert all(parent.token_count_p1_256 <= 256 for parent in parents)
    assert all(parent.token_count_p2_256 <= 256 for parent in parents)
    audit = hierarchy_audit_payload()
    assert audit["fullChildContentStored"] is False
    assert audit["fullParentContentStored"] is False
    assert "contentHashP1Max256" in audit["parentUnits"][0]


def test_parent_index_manifest_has_no_real_index_file() -> None:
    manifest = parent_index_manifest_payload()
    assert manifest["parentCount"] == 18
    assert manifest["childCount"] == 153
    assert manifest["realIndexFilesStored"] is False
    assert manifest["parentBm25IndexComplete"] is True
    assert manifest["parentDenseIndexComplete"] is True
