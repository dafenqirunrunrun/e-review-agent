import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from realworld_data_policy import REAL_MANIFEST_DIR, load_jsonl, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REAL_MANIFEST_DIR / "source_manifest"
AUDIT_DIR = REAL_MANIFEST_DIR / "audit"
DOSSIER = MANIFEST_DIR / "source_candidate_dossier.jsonl"
EVIDENCE_INDEX = MANIFEST_DIR / "source_evidence_index.jsonl"
MANUAL_APPROVAL = MANIFEST_DIR / "manual_source_approval.yaml"
DELEGATED_APPROVED = MANIFEST_DIR / "delegated_approved_sources.jsonl"
APPROVED_SOURCES = MANIFEST_DIR / "approved_sources.jsonl"
STATUS = AUDIT_DIR / "source_approval_status.json"
REPORT = ROOT / "docs" / "158_v1618_delegated_source_approval.md"


OFFICIAL_EVIDENCE = [
    {
        "source_id": "amazon_reviews_2023",
        "official_url": "https://amazon-reviews-2023.github.io/",
        "evidence_type": "official_project_page",
        "evidence_strength": "official_research_release",
        "short_evidence_summary": "Official McAuley Lab page lists Amazon Reviews 2023, review/meta download links, user reviews, item metadata, and review image URL fields.",
        "unresolved_issue": "No explicit dataset license or terms were found on the official project page during this delegated audit.",
    },
    {
        "source_id": "asap_chinese_reviews",
        "official_url": "https://github.com/Meituan-Dianping/ASAP",
        "evidence_type": "official_repository",
        "evidence_strength": "explicit",
        "short_evidence_summary": "Official repository exposes data files and Apache-2.0 repository license for ASAP Chinese restaurant reviews.",
        "unresolved_issue": "Repository code/data license needs to remain separated from any broader redistribution or training claim.",
    },
    {
        "source_id": "asap_chinese_reviews",
        "official_url": "https://api.github.com/repos/Meituan-Dianping/ASAP/contents/data",
        "evidence_type": "official_repository_api",
        "evidence_strength": "explicit",
        "short_evidence_summary": "Official GitHub API lists train.csv, dev.csv, and test.csv under the repository data directory.",
        "unresolved_issue": "Pilot must keep raw text outside Git and must not be promoted to formal external test.",
    },
    {
        "source_id": "jddc_2_multimodal",
        "official_url": "https://github.com/hrlinlp/jddc2.1",
        "evidence_type": "official_repository",
        "evidence_strength": "official_research_release",
        "short_evidence_summary": "Official repository documents JDDC 2.1 multimodal Chinese dialogue and indicates access by application rather than direct public data files.",
        "unresolved_issue": "No data access approval has been obtained in this project, so all actual data acquisition rights remain unavailable.",
    },
]


def fetch_evidence(row: dict) -> dict:
    request = Request(row["official_url"], headers={"User-Agent": "EReviewAgent-Audit/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read(262144)
            status = response.status
            title = ""
            text = body.decode("utf-8", errors="replace")
            lower = text.lower()
            start = lower.find("<title>")
            end = lower.find("</title>")
            if 0 <= start < end:
                title = text[start + 7 : end].strip()[:200]
            elif row["official_url"].endswith("/contents/data"):
                title = "GitHub API repository contents"
    except Exception as exc:
        body = repr(exc).encode("utf-8")
        status = 0
        title = "fetch_failed"
    item = dict(row)
    item.update(
        {
            "fetched_at": f"{date.today().isoformat()}T00:00:00+08:00",
            "http_status": status,
            "page_title": title,
            "content_sha256": hashlib.sha256(body).hexdigest(),
        }
    )
    return item


def manual_yaml() -> str:
    return """approval_version: "1.1"
approved_by_user: true
approved_at: "2026-07-14"
approval_method: "delegated_conservative_evidence_review"
legal_certification: false
approver_note: >
  User delegated internal project source review to the assistant in this conversation.
  This approval is limited to E-Review Agent private, non-public research pilot work.
  It is not legal advice and does not authorize model training, commercial use, or redistribution.
risk_acceptance_note: >
  For official research releases without complete per-right license text, only private local pilot
  use is conditionally approved. Raw text, raw images, URLs, and user identifiers must stay outside Git.

sources:
  amazon_reviews_2023:
    decision_status: conditionally_approved
    approval_scope: private_internal_pilot
    approve_text_internal_research: true
    approve_text_external_evaluation: false
    approve_text_model_training: false
    approve_text_redistribution: false
    approve_image_download: true
    approve_image_internal_inference: true
    approve_image_external_evaluation: false
    approve_image_model_training: false
    approve_image_redistribution: false
    approve_derived_features: true
    approve_case_corpus_usage: false
    approve_sft_usage: false
    approve_vlm_sft_usage: false
    evidence_strength: official_research_release
    risk_level: high
    conditions:
      - "Official project page and download links must remain reachable."
      - "Pilot text records are capped at 150 for this source."
      - "Pilot image groups are capped at 20 and raw images stay outside Git."
      - "User identifiers must be hashed or removed."
      - "No raw review text, image URL, or raw image may be committed."
    prohibited_uses:
      - "model_training"
      - "sft_or_dpo"
      - "redistribution"
      - "commercial_use"
      - "formal_external_test"
    evidence_refs:
      - "https://amazon-reviews-2023.github.io/"
    reviewed_at: "2026-07-14"
    review_note: "Conditionally approved only for private local pilot because the official research page provides data links but no complete explicit license terms were found."

  asap_chinese_reviews:
    decision_status: conditionally_approved
    approval_scope: private_internal_pilot
    approve_text_internal_research: true
    approve_text_external_evaluation: false
    approve_text_model_training: false
    approve_text_redistribution: false
    approve_image_download: false
    approve_image_internal_inference: false
    approve_image_external_evaluation: false
    approve_image_model_training: false
    approve_image_redistribution: false
    approve_derived_features: true
    approve_case_corpus_usage: false
    approve_sft_usage: false
    approve_vlm_sft_usage: false
    evidence_strength: explicit
    risk_level: medium
    conditions:
      - "Use as Chinese text-only private pilot."
      - "Pilot text records are capped at 150 for this source."
      - "Do not mark as multimodal."
      - "Raw text must stay outside Git."
    prohibited_uses:
      - "image_use"
      - "model_training"
      - "sft_or_dpo"
      - "redistribution"
      - "formal_external_test"
    evidence_refs:
      - "https://github.com/Meituan-Dianping/ASAP"
      - "https://github.com/Meituan-Dianping/ASAP/blob/master/LICENSE"
    reviewed_at: "2026-07-14"
    review_note: "Conditionally approved for private Chinese text pilot only; restaurant review domain bias remains."

  jddc_2_multimodal:
    decision_status: unavailable
    approval_scope: auxiliary_development_only
    approve_text_internal_research: false
    approve_text_external_evaluation: false
    approve_text_model_training: false
    approve_text_redistribution: false
    approve_image_download: false
    approve_image_internal_inference: false
    approve_image_external_evaluation: false
    approve_image_model_training: false
    approve_image_redistribution: false
    approve_derived_features: false
    approve_case_corpus_usage: false
    approve_sft_usage: false
    approve_vlm_sft_usage: false
    evidence_strength: official_research_release
    risk_level: high
    conditions:
      - "Requires separate official application before data use."
      - "Do not treat as product review data."
    prohibited_uses:
      - "data_download"
      - "image_use"
      - "model_training"
      - "redistribution"
      - "formal_external_test"
    evidence_refs:
      - "https://github.com/hrlinlp/jddc2.1"
    reviewed_at: "2026-07-14"
    review_note: "Unavailable because official data access approval has not been obtained."
"""


def approved_rows() -> list[dict]:
    return [
        {
            "source_id": "amazon_reviews_2023",
            "source_name": "Amazon Reviews 2023",
            "official_publisher": "McAuley Lab / UCSD",
            "official_url": "https://amazon-reviews-2023.github.io/",
            "license_name": "official_research_release_without_complete_license_terms",
            "license_url": None,
            "research_use_allowed": True,
            "redistribution_allowed": False,
            "derived_data_redistribution_allowed": False,
            "contains_review_text": True,
            "contains_images": True,
            "contains_rating": True,
            "contains_product_category": True,
            "contains_user_identifier": True,
            "contains_personal_information": True,
            "image_download_allowed": True,
            "image_internal_inference_allowed": True,
            "image_redistribution_allowed": False,
            "model_training_allowed": False,
            "approval_status": "delegated_conditionally_approved",
            "decision_status": "conditionally_approved",
            "approval_scope": "private_internal_pilot",
            "max_text_pilot_records": 150,
            "max_image_pilot_groups": 20,
            "max_image_files": 120,
        },
        {
            "source_id": "asap_chinese_reviews",
            "source_name": "ASAP Chinese Review Dataset",
            "official_publisher": "Meituan-Dianping dataset authors",
            "official_url": "https://github.com/Meituan-Dianping/ASAP",
            "license_name": "Apache-2.0 repository license",
            "license_url": "https://github.com/Meituan-Dianping/ASAP/blob/master/LICENSE",
            "research_use_allowed": True,
            "redistribution_allowed": False,
            "derived_data_redistribution_allowed": False,
            "contains_review_text": True,
            "contains_images": False,
            "contains_rating": True,
            "contains_product_category": True,
            "contains_user_identifier": False,
            "contains_personal_information": True,
            "image_download_allowed": False,
            "image_internal_inference_allowed": False,
            "image_redistribution_allowed": False,
            "model_training_allowed": False,
            "approval_status": "delegated_conditionally_approved",
            "decision_status": "conditionally_approved",
            "approval_scope": "private_internal_pilot",
            "max_text_pilot_records": 150,
            "max_image_pilot_groups": 0,
            "max_image_files": 0,
        },
    ]


def status_payload(rows: list[dict]) -> dict:
    return {
        "marker": "DELEGATED_SOURCE_APPROVAL_COMPLETE",
        "stage": "v1.6.1.8-delegated-source-approval-and-private-pilot",
        "approved_by_user": True,
        "approval_method": "delegated_conservative_evidence_review",
        "legal_certification": False,
        "candidate_source_count": len(load_jsonl(DOSSIER)),
        "conditionally_approved_sources": [row["source_id"] for row in rows],
        "unavailable_sources": ["jddc_2_multimodal"],
        "text_pilot_status": "REAL_TEXT_PILOT_ACQUISITION_ALLOWED",
        "multimodal_pilot_status": "REAL_MULTIMODAL_PILOT_ACQUISITION_ALLOWED",
        "formal_external_test_status": "NOT_APPROVED",
        "model_training_status": "NOT_APPROVED",
        "redistribution_status": "NOT_APPROVED",
        "manual_approval_file": "data/real_world/source_manifest/manual_source_approval.yaml",
    }


def report(evidence: list[dict], rows: list[dict], status: dict) -> str:
    evidence_rows = "\n".join(
        f"| `{row['source_id']}` | {row['http_status']} | {row['evidence_strength']} | {row['official_url']} | {row['unresolved_issue']} |"
        for row in evidence
    )
    approved_rows_md = "\n".join(
        f"| `{row['source_id']}` | {row['decision_status']} | {row['approval_scope']} | {row['contains_review_text']} | {row['contains_images']} | {row['model_training_allowed']} | {row['redistribution_allowed']} |"
        for row in rows
    )
    return f"""# v1.6.1.8 Delegated Real-World Source Approval

## Conclusion

`{status['marker']}`

The user delegated conservative project-internal source review to the assistant.
This is not legal certification. Training, commercial use, redistribution, and
formal external-test use remain disallowed.

## Official Evidence Recheck

| Source | HTTP | Strength | Official URL | Unresolved issue |
| --- | ---: | --- | --- | --- |
{evidence_rows}

## Conditional Approval

| Source | Decision | Scope | Text | Images | Training | Redistribution |
| --- | --- | --- | --- | --- | --- | --- |
{approved_rows_md}
| `jddc_2_multimodal` | unavailable | auxiliary_development_only | false | false | false | false |

## Gate Effects

- `REAL_TEXT_PILOT_ACQUISITION_ALLOWED`
- `REAL_MULTIMODAL_PILOT_ACQUISITION_ALLOWED`
- Formal external test: not approved
- SFT/DPO/VLM fine-tuning: not approved
- Raw pilot data must stay outside Git under `D:\\EReviewAgent\\data-private\\realworld-pilot`
"""


def main() -> int:
    evidence = [fetch_evidence(row) for row in OFFICIAL_EVIDENCE]
    rows = approved_rows()
    status = status_payload(rows)
    MANUAL_APPROVAL.write_text(manual_yaml(), encoding="utf-8", newline="\n")
    write_jsonl(EVIDENCE_INDEX, evidence)
    write_jsonl(DELEGATED_APPROVED, rows)
    write_jsonl(APPROVED_SOURCES, rows)
    write_json(STATUS, status)
    REPORT.write_text(report(evidence, rows, status), encoding="utf-8", newline="\n")
    print(json.dumps(status, ensure_ascii=False))
    print(status["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
