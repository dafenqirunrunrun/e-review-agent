from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.contracts.governance_history import CURRENT_GOVERNANCE_SCHEMA_VERSION, adapt_snapshot_for_display, migrate_snapshot


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "governance_history_rows.json"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("governance_migration", ROOT / "scripts" / "migrate_review_governance_history.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v1_snapshot_migrates_losslessly_to_current_schema():
    snapshot = {"schemaVersion": "review-governance-v1", "riskTypes": ["rating_manipulation"], "evidenceStatus": "supported", "decision": {"code": "manual_review"}}

    migrated = migrate_snapshot(snapshot, review_text="五星截图返现")

    assert migrated.outcome == "migrated"
    assert migrated.snapshot["schemaVersion"] == CURRENT_GOVERNANCE_SCHEMA_VERSION
    assert migrated.snapshot["governanceSchemaVersion"] == CURRENT_GOVERNANCE_SCHEMA_VERSION
    assert migrated.snapshot["originalGovernanceSnapshot"] == snapshot
    assert migrated.snapshot["riskCoverage"][0]["label"] == "评分操纵"


def test_unknown_risk_is_preserved_instead_of_guessed():
    migrated = migrate_snapshot({"schemaVersion": "review-governance-v1", "riskTypes": ["legacy_unclassified"], "decision": {"code": "manual_review"}})

    assert migrated.outcome == "unknown"
    assert migrated.unknown_risk_types == ["legacy_unclassified"]
    assert migrated.snapshot["riskTypes"] == ["legacy_unclassified"]


def test_historical_cashback_conflict_requires_reevaluation_not_semantic_rewrite():
    migrated = migrate_snapshot(
        {"schemaVersion": "review-governance-v1", "riskTypes": ["after_sales_risk", "rating_manipulation"], "evidenceStatus": "mismatch", "decision": {"code": "manual_review"}},
        review_text="五星截图返现，晒图后返10元。",
    )

    assert migrated.outcome == "requires_reevaluation"
    assert migrated.requires_reevaluation is True
    assert migrated.snapshot["riskTypes"] == ["after_sales_risk", "rating_manipulation"]
    assert migrated.snapshot["historyDisplay"]["message"].startswith("历史判断")


def test_current_snapshot_is_idempotent_and_display_adapter_keeps_v1_renderable():
    current = {"schemaVersion": CURRENT_GOVERNANCE_SCHEMA_VERSION, "riskTypes": ["normal_review"]}

    assert migrate_snapshot(current).outcome == "already_current"
    adapted = adapt_snapshot_for_display({"schemaVersion": "review-governance-v1", "riskTypes": ["normal_review"], "decision": {"code": "auto_pass"}})
    assert adapted["schemaVersion"] == CURRENT_GOVERNANCE_SCHEMA_VERSION
    assert adapted["historyDisplay"]["isHistorical"] is True


def test_legacy_auto_pass_without_evidence_status_stays_business_consistent():
    migrated = migrate_snapshot({"schemaVersion": "review-governance-v1", "decision": {"code": "auto_pass"}})

    assert migrated.snapshot["riskTypes"] == ["normal_review"]
    assert migrated.snapshot["evidenceStatus"] == "supported"
    assert migrated.snapshot["riskCoverage"][0]["status"] == "supported"


def test_controlled_fixture_reports_seven_rows_and_preserves_human_terminal_fields():
    module = _load_script_module()
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    args = type("Args", (), {"from_version": "review-governance-v1", "to_version": CURRENT_GOVERNANCE_SCHEMA_VERSION})()

    report = module._report(rows, args)
    human = next(item for item in report["items"] if item.get("reviewId") == "legacy-human-resolved")

    assert report["total"] == 7
    assert report["migratable"] >= 2
    assert report["unknown"] == 2
    assert report["conflict"] == 1
    assert report["alreadyCurrent"] == 1
    assert human["humanResolved"] is True
    assert human["migratedSnapshot"]["migration"]["humanResolvedAtMigration"] is True
    assert human["migratedSnapshot"]["originalGovernanceSnapshot"]["riskTypes"] == ["after_sales_risk"]


def test_repeated_migration_is_idempotent():
    first = migrate_snapshot({"schemaVersion": "review-governance-v1", "riskTypes": ["paid_review_risk"], "evidenceStatus": "supported", "decision": {"code": "suggest_action"}})
    second = migrate_snapshot(first.snapshot)

    assert first.snapshot["riskTypes"] == ["paid_review"]
    assert second.outcome == "already_current"
    assert second.snapshot == first.snapshot
