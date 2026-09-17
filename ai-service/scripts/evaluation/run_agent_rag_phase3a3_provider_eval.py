from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a2_common import phase3a2_cases, split_cases
from agent_rag_phase3a3_common import PROVIDER_IMPLS, benchmark_payload, hash_payload, metric_summary_for_provider, write_phase3a3_json
from agent_rag_phase3a_common import source_commit


def run() -> dict:
    _, evaluation, chunks, ingestion = benchmark_payload()
    cases = phase3a2_cases(chunks)
    split = split_cases(cases)
    providers = {impl: metric_summary_for_provider(impl) for impl in PROVIDER_IMPLS}
    flag = providers["flagembedding"]
    legacy = providers["legacy-cls"]
    if flag["status"] != "PASS":
        conclusion = "AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_BLOCKED"
        selected = "legacy-cls"
    elif legacy["status"] == "PASS" and flag["evaluation"]["subsets"]["overall"]["bge"]["ndcgAt5"] > legacy["evaluation"]["subsets"]["overall"]["bge"]["ndcgAt5"] + 0.02:
        conclusion = "AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_IMPROVED"
        selected = "flagembedding"
    elif legacy["status"] == "PASS" and flag["evaluation"]["subsets"]["overall"]["bge"]["ndcgAt5"] + 0.02 < legacy["evaluation"]["subsets"]["overall"]["bge"]["ndcgAt5"]:
        conclusion = "AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_REGRESSION"
        selected = "legacy-cls"
    else:
        conclusion = "AGENT_RAG_OFFICIAL_PROVIDER_PARITY_ONLY"
        selected = "flagembedding"
    output = {
        "schemaVersion": "1.0.0",
        "sourceCommit": source_commit(),
        "benchmarkVersion": "phase3a2-stratified-v1",
        "benchmarkHash": hash_payload({"cases": cases}),
        "knowledgeRootHash": hash_payload({"chunks": [chunk.contentHash for chunk in chunks]}),
        "evaluationCaseIdsHash": split["evaluationCaseIdsHash"],
        "fusionConfigHash": hash_payload({"strategy": "weighted-rrf", "sparseWeight": 1.0, "denseWeight": 0.5, "rrfK": 60}),
        "providers": providers,
        "qualityConclusion": conclusion,
        "selectedProviderImpl": selected,
        "defaultRetrievalMode": "bm25-first-semantic-hybrid",
        "ingestion": ingestion,
    }
    write_phase3a3_json("provider-evaluation-summary.json", output)
    (write_phase3a3_json.__globals__["PHASE3A3_OUT"] / "provider-evaluation-report.md").write_text(
        "\n".join([
            "# Phase 3A.3 Provider Evaluation",
            "",
            f"- Quality conclusion: `{conclusion}`",
            f"- Selected provider: `{selected}`",
            f"- FlagEmbedding status: `{flag['status']}`",
            f"- Sentence Transformers status: `{providers['sentence-transformers']['status']}`",
        ]) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
