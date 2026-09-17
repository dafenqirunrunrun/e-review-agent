from __future__ import annotations

import json

from v23_retrieval_common import DOCS, OUT, build_v23_cases, hash_json, write_json, write_text
from v23_retrieval_v2_common import DATASET_VERSION, build_v23_v2_cases, build_v23_v2_manifest


def main() -> int:
    cases = build_v23_v2_cases()
    manifest = build_v23_v2_manifest(cases)
    old = build_v23_cases()
    old_query_hashes = {case["queryHash"] for case in old}
    new_query_hashes = {case["queryHash"] for case in cases}
    audit = {
        "schemaVersion": "agent-rag-v23-retrieval-dataset-v2-audit-v1",
        "datasetVersion": DATASET_VERSION,
        "manifest": manifest,
        "oldCaseCount": len(old),
        "oldQueryHashIntersectionCount": len(old_query_hashes & new_query_hashes),
        "oldCaseIdIntersectionCount": len({case["caseId"] for case in old} & {case["caseId"] for case in cases}),
        "caseFamilyLeakageCount": leakage_count(cases, "caseFamilyId"),
        "documentFamilyLeakageCount": leakage_count([case for case in cases if case["label"] == "answerable"], "documentFamilyId"),
        "answerableLabelAuditComplete": all(case["minimumRelevantCount"] >= 1 and case["expectedRelevantChunkIds"] for case in cases if case["label"] == "answerable"),
        "noAnswerCorpusAuditComplete": all(case["minimumRelevantCount"] == 0 and case["corpusAuditHash"] for case in cases if case["label"] == "no_answer"),
        "intentMaxSpread": distribution_max_spread(manifest["splitIntentDistribution"]),
        "difficultyMaxSpread": distribution_max_spread(manifest["splitDifficultyDistribution"]),
        "artifactPolicy": "full queries are generated in code but not written to audit artifacts",
        "datasetLightHash": hash_json(light_cases(cases)),
    }
    write_json(OUT / "v23-retrieval-qualification-v2-audit.json", audit)
    write_json(OUT / "v23-retrieval-qualification-v2-manifest.json", manifest)
    write_text(DOCS / "V23_RETRIEVAL_QUALIFICATION_V2.md", render_doc(audit))
    print("E_REVIEW_V23_RETRIEVAL_DATASET_V2_BUILD_COMPLETE")
    print(manifest["datasetHash"])
    return 0


def leakage_count(cases: list[dict], key: str) -> int:
    split_by_key = {}
    for case in cases:
        split_by_key.setdefault(case[key], set()).add(case["split"])
    return sum(1 for splits in split_by_key.values() if len(splits) > 1)


def distribution_max_spread(distributions: dict[str, dict[str, float]]) -> float:
    keys = sorted({key for values in distributions.values() for key in values})
    max_spread = 0.0
    for key in keys:
        rates = [values.get(key, 0.0) for values in distributions.values()]
        max_spread = max(max_spread, max(rates) - min(rates))
    return round(max_spread, 6)


def light_cases(cases: list[dict]) -> list[dict]:
    return [
        {
            "caseId": case["caseId"],
            "caseFamilyId": case["caseFamilyId"],
            "documentFamilyId": case["documentFamilyId"],
            "split": case["split"],
            "label": case["label"],
            "queryIntent": case["queryIntent"],
            "difficulty": case["difficulty"],
            "queryHash": case["queryHash"],
            "relevantHash": hash_json(case["expectedRelevantChunkIds"] + case["acceptableRelevantChunkIds"]),
        }
        for case in cases
    ]


def render_doc(audit: dict) -> str:
    return "# V2.3 Retrieval Qualification Benchmark V2\n\n```json\n" + json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


if __name__ == "__main__":
    raise SystemExit(main())
