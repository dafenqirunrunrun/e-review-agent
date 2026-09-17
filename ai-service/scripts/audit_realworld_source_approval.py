import json
import re
from pathlib import Path

from realworld_data_policy import REAL_MANIFEST_DIR, load_jsonl, write_json


ROOT = Path(__file__).resolve().parents[2]
DOSSIER = REAL_MANIFEST_DIR / "source_manifest" / "source_candidate_dossier.jsonl"
APPROVAL = REAL_MANIFEST_DIR / "source_manifest" / "manual_source_approval.yaml"
OUT = REAL_MANIFEST_DIR / "audit" / "source_approval_status.json"
REPORT = ROOT / "docs" / "154_v1617_realworld_source_candidate_dossier.md"

RIGHT_KEYS = [
    "approve_text_internal_research",
    "approve_text_model_training",
    "approve_text_redistribution",
    "approve_image_download",
    "approve_image_internal_inference",
    "approve_image_model_training",
    "approve_image_redistribution",
    "approve_derived_features",
]


def approval_text() -> str:
    return APPROVAL.read_text(encoding="utf-8") if APPROVAL.exists() else ""


def approved_by_user(text: str) -> bool:
    return re.search(r"(?m)^approved_by_user:\s*true\s*$", text) is not None


def source_block(text: str, source_id: str) -> str:
    pattern = rf"(?ms)^\s{{2}}{re.escape(source_id)}:\n(.*?)(?=^\s{{2}}\w|\Z)"
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def approved_rights(text: str, source_id: str) -> dict[str, bool]:
    block = source_block(text, source_id)
    return {
        key: re.search(rf"(?m)^\s{{4}}{re.escape(key)}:\s*true\s*$", block) is not None
        for key in RIGHT_KEYS
    }


def build_report(candidates: list[dict], status: dict) -> str:
    rows = []
    detail_sections = []
    for row in candidates:
        rights = row.get("rights_decisions", {})
        rows.append(
            "| `{source_id}` | {text} | {images} | {language} | {internal_eval} | {training} | {redistribution} | {issue} |".format(
                source_id=row["source_id"],
                text="yes" if row.get("review_text_available") else "no",
                images="yes" if row.get("user_review_images_available") else "no",
                language=row.get("language", "unknown"),
                internal_eval="pending user approval" if rights.get("text_internal_research_allowed") is False else "allowed",
                training="not approved",
                redistribution="not approved",
                issue="; ".join(row.get("unresolved_questions", [])[:1]) or "manual approval required",
            )
        )
        detail_sections.append(
            f"""## {row['source_id']}

- Official source: {row.get('official_project_url')}
- Official paper: {row.get('official_paper_url')}
- License evidence: {row.get('official_license_url') or 'not found / not explicit'}
- Recommended use: {row.get('recommended_use')}
- Prohibited use: {row.get('prohibited_use')}
- Contact authors recommended: {row.get('contact_authors_recommended')}
- External test suitability: not yet; source approval and pilot isolation are required first.
- SFT suitability: not yet; no training rights are approved.
- Missing evidence: {'; '.join(row.get('unresolved_questions', []))}
""".rstrip()
        )
    table = "\n".join(rows)
    details = "\n".join(detail_sections)
    return f"""# v1.6.1.7 Real-World Source Candidate Dossier

## Gate

`{status['marker']}`

Codex generated this dossier for manual review only. It does not approve any
source, does not download data, and does not start a pilot.

## Decision Table

| Source | Text | Images | Language | Internal evaluation | Training | Redistribution | Main unresolved issue |
| --- | --- | --- | --- | --- | --- | --- | --- |
{table}

## Candidate Details

{details}
""".rstrip() + "\n"


def main() -> int:
    candidates = load_jsonl(DOSSIER)
    text = approval_text()
    user_approved = approved_by_user(text)
    source_rights = {row["source_id"]: approved_rights(text, row["source_id"]) for row in candidates}
    approved_sources = [
        source_id
        for source_id, rights in source_rights.items()
        if user_approved and any(rights.values())
    ]
    status = {
        "marker": "REALWORLD_SOURCE_APPROVAL_REQUIRED" if not approved_sources else "REALWORLD_SOURCE_APPROVAL_REVIEWED",
        "stage": "v1.6.1.7-realworld-source-approval-and-pilot-acquisition",
        "candidate_source_count": len(candidates),
        "approved_by_user": user_approved,
        "approved_source_count": len(approved_sources),
        "approved_text_source_count": sum(
            1
            for row in candidates
            if row["source_id"] in approved_sources and source_rights[row["source_id"]].get("approve_text_internal_research")
        ),
        "approved_multimodal_source_count": sum(
            1
            for row in candidates
            if row["source_id"] in approved_sources and source_rights[row["source_id"]].get("approve_image_internal_inference")
        ),
        "pilot_acquisition_allowed": False,
        "blocking_reasons": []
        if approved_sources
        else [
            "manual_source_approval.yaml has approved_by_user=false",
            "no source has user-approved text, image, training, redistribution, or derived-feature rights",
            "pilot acquisition must not run before explicit user approval",
        ],
        "manual_approval_file": str(APPROVAL.relative_to(ROOT)).replace("\\", "/"),
        "source_rights": source_rights,
    }
    write_json(OUT, status)
    REPORT.write_text(build_report(candidates, status), encoding="utf-8", newline="\n")
    print(json.dumps(status, ensure_ascii=False))
    print(status["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
