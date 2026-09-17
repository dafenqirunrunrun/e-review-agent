import argparse
import hashlib
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag_v2.corpus_loader import case_text, load_jsonl
from app.rag_v2.dense_encoder import BgeM3Encoder


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_ROOT = ROOT / "data" / "rag" / "audit"
DEFAULT_REPORT_PATH = ROOT / "docs" / "108_v161_synthetic_data_leakage_audit.md"
RISK_ENUMS = {"after_sales_risk", "negative_review", "normal_review"}
RISK_LEVELS = {"low", "medium", "high"}


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def normalize_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", (value or "").lower(), flags=re.UNICODE)


def char_ngrams(value: str, n: int = 3) -> set:
    text = normalize_text(value)
    if len(text) <= n:
        return {text} if text else set()
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def jaccard(left: str, right: str) -> float:
    a = char_ngrams(left)
    b = char_ngrams(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def doc_id(prefix: str, row: Dict) -> str:
    for key in ("review_id", "case_id", "query_id"):
        if key in row:
            return f"{prefix}:{row[key]}"
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return f"{prefix}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def doc_text(prefix: str, row: Dict) -> str:
    if prefix == "comment":
        return row.get("review_text") or ""
    if prefix == "case":
        return case_text(row)
    return row.get("query_text") or ""


def build_docs(comments: List[Dict], cases: List[Dict], queries: List[Dict]) -> List[Dict]:
    docs = []
    for prefix, rows in (("comment", comments), ("case", cases), ("query", queries)):
        for row in rows:
            text = doc_text(prefix, row)
            docs.append({"doc_id": doc_id(prefix, row), "kind": prefix, "text": text, "row": row})
    return docs


def duplicate_rows(docs: List[Dict], normalized: bool) -> List[Dict]:
    groups = defaultdict(list)
    for doc in docs:
        key = normalize_text(doc["text"]) if normalized else doc["text"].strip()
        if key:
            groups[key].append(doc)
    rows = []
    for key, group in groups.items():
        kinds = sorted({item["kind"] for item in group})
        if len(group) > 1 and len(kinds) > 1:
            rows.append({
                "text_key": key[:160],
                "doc_ids": [item["doc_id"] for item in group],
                "kinds": kinds,
                "count": len(group),
            })
    return rows


def tfidf_pair_scores(left: Sequence[str], right: Sequence[str]) -> List[List[float]]:
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(list(left) + list(right))
    scores = cosine_similarity(matrix[: len(left)], matrix[len(left) :])
    return scores.tolist()


def query_case_overlap(queries: List[Dict], cases: List[Dict]) -> Tuple[List[Dict], List[float]]:
    query_texts = [row.get("query_text", "") for row in queries]
    case_texts = [case_text(row) for row in cases]
    tfidf = tfidf_pair_scores(query_texts, case_texts)
    case_by_id = {row["case_id"]: row for row in cases}
    rows = []
    all_relevant_scores = []
    for q_index, query in enumerate(queries):
        relevant = [case_by_id[case_id] for case_id in query.get("relevant_case_ids", []) if case_id in case_by_id]
        relevant_indexes = [cases.index(row) for row in relevant]
        lexical_scores = [tfidf[q_index][index] for index in relevant_indexes]
        jaccard_scores = [jaccard(query.get("query_text", ""), case_text(row)) for row in relevant]
        max_tfidf = max(lexical_scores) if lexical_scores else 0.0
        max_jaccard = max(jaccard_scores) if jaccard_scores else 0.0
        all_relevant_scores.append(max_tfidf)
        if max_tfidf >= 0.45 or max_jaccard >= 0.35:
            rows.append({
                "query_id": query["query_id"],
                "max_relevant_tfidf_cosine": round(max_tfidf, 6),
                "max_relevant_char3_jaccard": round(max_jaccard, 6),
                "query_text": query.get("query_text", "")[:200],
                "relevant_case_ids": query.get("relevant_case_ids", []),
            })
    return rows, all_relevant_scores


def bge_query_case_overlap(queries: List[Dict], cases: List[Dict], model_dir: Path, device: str) -> Tuple[Dict, Dict[str, float]]:
    if not model_dir or not model_dir.exists():
        return {"checked": False, "reason": "BGE_M3_MODEL_DIR_NOT_AVAILABLE"}, {}
    encoder = BgeM3Encoder(model_dir=model_dir, device=device, batch_size=8, normalize=True, max_length=512)
    if not encoder.available:
        return {"checked": False, "reason": "BGE_M3_MODEL_NOT_AVAILABLE"}, {}
    try:
        query_vectors = encoder.encode_queries([row.get("query_text", "") for row in queries])
        case_vectors = encoder.encode_documents([case_text(row) for row in cases])
    finally:
        encoder.unload()
    scores = query_vectors @ case_vectors.T
    case_index = {row["case_id"]: index for index, row in enumerate(cases)}
    relevant_scores = []
    high_rows = []
    for q_index, query in enumerate(queries):
        indexes = [case_index[case_id] for case_id in query.get("relevant_case_ids", []) if case_id in case_index]
        values = [float(scores[q_index][index]) for index in indexes]
        max_score = max(values) if values else 0.0
        relevant_scores.append(max_score)
        if max_score >= 0.90:
            high_rows.append({
                "query_id": query["query_id"],
                "max_relevant_bge_m3_cosine": round(max_score, 6),
                "relevant_case_ids": query.get("relevant_case_ids", []),
            })
    stats = summarize(relevant_scores)
    stats.update({
        "checked": True,
        "device": encoder.device,
        "high_bge_overlap_query_count": len(high_rows),
        "high_bge_overlap_query_rate": round(len(high_rows) / max(1, len(queries)), 6),
        "high_rows": high_rows,
    })
    return stats, {row["query_id"]: row["max_relevant_bge_m3_cosine"] for row in high_rows}


def near_duplicate_rows(docs: List[Dict]) -> List[Dict]:
    rows = []
    for left, right in combinations(docs, 2):
        if left["kind"] == right["kind"]:
            continue
        score = jaccard(left["text"], right["text"])
        if score >= 0.60:
            rows.append({
                "left_id": left["doc_id"],
                "right_id": right["doc_id"],
                "char3_jaccard": round(score, 6),
                "left_text": left["text"][:160],
                "right_text": right["text"][:160],
            })
    return rows


def template_family_key(row: Dict) -> str:
    case_id = row.get("case_id") or ""
    query_id = row.get("query_id") or ""
    review_id = row.get("review_id") or ""
    source = case_id or query_id or review_id
    if source:
        return re.sub(r"-\d+$", "", source)
    text = doc_text("case", row)
    text = re.sub(r"[“\"].+?[”\"]", "QUOTE", text)
    text = re.sub(r"\d+", "N", text)
    return normalize_text(text)[:80]


def template_families(comments: List[Dict], cases: List[Dict], queries: List[Dict]) -> Dict:
    groups = defaultdict(list)
    for prefix, rows in (("comment", comments), ("case", cases), ("query", queries)):
        for row in rows:
            groups[template_family_key(row)].append(doc_id(prefix, row))
    suspected = {key: ids for key, ids in groups.items() if len(ids) >= 4}
    return {
        "suspected_template_family_count": len(suspected),
        "families": dict(sorted(suspected.items(), key=lambda item: (-len(item[1]), item[0]))),
    }


def metadata_shortcuts(queries: List[Dict], retriever_paths: Sequence[Path]) -> List[Dict]:
    rows = []
    for query in queries:
        query_text = query.get("query_text", "")
        for field in ("expected_risk_type", "expected_risk_level"):
            value = query.get(field)
            if value and value in query_text:
                rows.append({"query_id": query["query_id"], "field": field, "shortcut_type": "answer_field_literal_in_query"})
        for case_id in query.get("relevant_case_ids", []):
            if case_id in query_text:
                rows.append({"query_id": query["query_id"], "field": "relevant_case_ids", "shortcut_type": "case_id_literal_in_query"})
        for keyword in query.get("evidence_keywords", []):
            if keyword and keyword in query_text:
                rows.append({"query_id": query["query_id"], "field": "evidence_keywords", "value": keyword, "shortcut_type": "gold_evidence_keyword_in_query"})
    source = "\n".join(path.read_text(encoding="utf-8") for path in retriever_paths if path.exists())
    code_checks = {
        "expected_risk_type_passed_as_risk_type": "risk_type" in source and "expected_risk_type" not in source,
        "metadata_match_score_uses_risk_type": "metadata_match_score" in source and "request.get(\"risk_type\")" in source,
        "metadata_match_score_uses_risk_level": "request.get(\"risk_level\")" in source,
        "metadata_match_score_uses_product_category": "request.get(\"product_category\")" in source,
        "rule_reranker_uses_evidence_keywords": "evidence_keywords" in source,
        "rule_reranker_uses_hard_negative_case_ids": "hard_negative_case_ids" in source,
    }
    for name, present in code_checks.items():
        if present:
            rows.append({"scope": "code", "shortcut_type": name, "severity": "high" if "risk_type" in name or "risk_level" in name else "medium"})
    return rows


def summarize(scores: List[float]) -> Dict:
    if not scores:
        return {"mean": 0.0, "p95": 0.0}
    ordered = sorted(scores)
    p95_index = max(0, int(len(ordered) * 0.95 + 0.999999) - 1)
    return {"mean": round(statistics.mean(scores), 6), "p95": round(ordered[p95_index], 6)}


def report_text(summary: Dict, marker: str) -> str:
    lines = [
        "# v1.6.1 模拟数据泄漏审计报告",
        "",
        f"审计标记：`{marker}`",
        "",
        "本报告审计 v1.6 合成评论、合成案例和 80 条黄金查询是否存在重复、模板化、查询-案例高重叠以及答案字段/元数据捷径。审计结果用于解释 Hit@3/Hit@5=100% 的可信边界，不覆盖 v1.6 原始评测文件。",
        "",
        "## 汇总指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
    ]
    for key in [
        "exact_duplicate_count",
        "normalized_duplicate_count",
        "near_duplicate_count",
        "suspected_template_family_count",
        "query_case_overlap_mean",
        "query_case_overlap_p95",
        "high_overlap_query_rate",
        "bge_m3_overlap_mean",
        "bge_m3_overlap_p95",
        "high_bge_overlap_query_rate",
        "metadata_shortcut_count",
        "answer_field_leakage_count",
    ]:
        lines.append(f"| {key} | {summary[key]} |")
    lines.extend([
        "",
        "## 关键发现",
        "",
        f"- 完全重复跨集合数量：{summary['exact_duplicate_count']}；归一化重复跨集合数量：{summary['normalized_duplicate_count']}。",
        f"- 高重叠查询数量：{summary['high_overlap_query_count']} / {summary['query_count']}。",
        f"- BGE-M3 cosine 审计：checked={summary['bge_m3_cosine_checked']}，mean={summary['bge_m3_overlap_mean']}，p95={summary['bge_m3_overlap_p95']}。",
        f"- 模板家族数量：{summary['suspected_template_family_count']}。v1.6 数据由固定场景模板生成，该结果说明 100% 检索命中不能直接外推到真实表达。",
        f"- 元数据/答案字段捷径数量：{summary['metadata_shortcut_count']}。当前 Oracle 评测路径把期望风险类型/等级作为 request metadata 参与排序，必须新增 No-Oracle 评估。",
        "",
        "## 文件产物",
        "",
        "- `data/rag/audit/exact_duplicates.jsonl`",
        "- `data/rag/audit/normalized_duplicates.jsonl`",
        "- `data/rag/audit/near_duplicates.jsonl`",
        "- `data/rag/audit/template_families.json`",
        "- `data/rag/audit/high_overlap_queries.jsonl`",
        "- `data/rag/audit/metadata_shortcuts.jsonl`",
        "- `data/rag/audit/leakage_audit_summary.json`",
        "",
        "## 结论",
        "",
        "v1.6 的 Hybrid RAG 结果可作为工程回归基线，但存在明显的模板数据与 Oracle metadata 评估风险。v1.6.1 后续必须使用 strict 模拟集、真实外部集和 No-Oracle 模式重新评估，不得仅凭原 80 条黄金查询宣布泛化能力。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments", type=Path, default=ROOT / "data/rag/comments/review_samples_1200.jsonl")
    parser.add_argument("--cases", type=Path, default=ROOT / "data/rag/cases/risk_cases_240.jsonl")
    parser.add_argument("--queries", type=Path, default=ROOT / "data/rag/golden_queries/golden_queries_80.jsonl")
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--bge-model-dir", type=Path, default=Path("D:/EReviewAgent/models/bge-m3"))
    parser.add_argument("--bge-device", default="cuda")
    args = parser.parse_args()

    comments = load_jsonl(args.comments)
    cases = load_jsonl(args.cases)
    queries = load_jsonl(args.queries)
    docs = build_docs(comments, cases, queries)

    exact = duplicate_rows(docs, normalized=False)
    normalized = duplicate_rows(docs, normalized=True)
    near = near_duplicate_rows(docs)
    overlap_rows, overlap_scores = query_case_overlap(queries, cases)
    bge_stats, high_bge_by_query = bge_query_case_overlap(queries, cases, args.bge_model_dir, args.bge_device)
    for row in overlap_rows:
        if row["query_id"] in high_bge_by_query:
            row["max_relevant_bge_m3_cosine"] = high_bge_by_query[row["query_id"]]
    families = template_families(comments, cases, queries)
    shortcuts = metadata_shortcuts(queries, [
        ROOT / "ai-service/app/rag_v2/hybrid_retriever.py",
        ROOT / "ai-service/app/rag_v2/reranker.py",
        ROOT / "ai-service/app/rag_v2/evaluator.py",
        ROOT / "ai-service/scripts/eval_hybrid_rag.py",
    ])

    overlap = summarize(overlap_scores)
    answer_leakage = sum(1 for row in shortcuts if row.get("field") in {"expected_risk_type", "expected_risk_level", "relevant_case_ids", "evidence_keywords"})
    summary = {
        "comment_count": len(comments),
        "case_count": len(cases),
        "query_count": len(queries),
        "exact_duplicate_count": len(exact),
        "normalized_duplicate_count": len(normalized),
        "near_duplicate_count": len(near),
        "suspected_template_family_count": families["suspected_template_family_count"],
        "query_case_overlap_mean": overlap["mean"],
        "query_case_overlap_p95": overlap["p95"],
        "high_overlap_query_count": len(overlap_rows),
        "high_overlap_query_rate": round(len(overlap_rows) / max(1, len(queries)), 6),
        "bge_m3_cosine_checked": bool(bge_stats.get("checked")),
        "bge_m3_overlap_mean": bge_stats.get("mean", 0.0),
        "bge_m3_overlap_p95": bge_stats.get("p95", 0.0),
        "high_bge_overlap_query_count": bge_stats.get("high_bge_overlap_query_count", 0),
        "high_bge_overlap_query_rate": bge_stats.get("high_bge_overlap_query_rate", 0.0),
        "bge_m3_audit_device": bge_stats.get("device"),
        "bge_m3_audit_reason": bge_stats.get("reason"),
        "metadata_shortcut_count": len(shortcuts),
        "answer_field_leakage_count": answer_leakage,
        "notes": [
            "Oracle metadata shortcut is present because evaluator request fields include risk_type/risk_level derived from expected labels and retriever scoring uses them.",
        ],
    }
    if bge_stats.get("high_rows"):
        existing = {row["query_id"] for row in overlap_rows}
        for row in bge_stats["high_rows"]:
            if row["query_id"] not in existing:
                overlap_rows.append(row)

    args.audit_root.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.audit_root / "exact_duplicates.jsonl", exact)
    write_jsonl(args.audit_root / "normalized_duplicates.jsonl", normalized)
    write_jsonl(args.audit_root / "near_duplicates.jsonl", near)
    write_jsonl(args.audit_root / "high_overlap_queries.jsonl", overlap_rows)
    write_jsonl(args.audit_root / "metadata_shortcuts.jsonl", shortcuts)
    (args.audit_root / "template_families.json").write_text(
        json.dumps(families, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (args.audit_root / "leakage_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    marker = "RAG_LEAKAGE_AUDIT_COMPLETE"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text(summary, marker), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
