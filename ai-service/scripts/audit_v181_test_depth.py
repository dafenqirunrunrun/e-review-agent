from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "private_research" / "audit" / "v181_test_depth_audit.json"
BASELINE = "94ff37e3"


@dataclass(frozen=True)
class TestFunction:
    path: str
    name: str
    line: int
    parametrized_cases: int
    category: str
    semantics: str
    uses_mock: bool
    uses_fake_retriever: bool
    uses_monkeypatch: bool
    asserts_status_only: bool

    @property
    def key(self) -> str:
        return f"{self.path}::{self.name}"


def main() -> None:
    baseline = _collect_baseline()
    current = _collect_current()
    baseline_keys = {row.key for row in baseline}
    current_keys = {row.key for row in current}
    added = [row for row in current if row.key not in baseline_keys]
    removed = [row for row in baseline if row.key not in current_keys]

    category_counts = _count(row.category for row in added)
    semantics_counts = _count(row.semantics for row in added)
    result = {
        "baseline_commit": BASELINE,
        "baseline_test_functions": len(baseline),
        "current_test_functions": len(current),
        "physical_added_test_functions": len(added),
        "removed_test_functions": len(removed),
        "net_test_growth": len(current) - len(baseline),
        "parametrized_case_count_added": sum(row.parametrized_cases for row in added),
        "category_counts_added": category_counts,
        "semantics_counts_added": semantics_counts,
        "unit_count": category_counts.get("unit", 0),
        "integration_count": category_counts.get("integration", 0),
        "security_count": category_counts.get("security", 0),
        "persistence_count": category_counts.get("persistence", 0),
        "http_count": category_counts.get("http", 0),
        "real_faiss_count": category_counts.get("real_faiss", 0),
        "real_embedding_count": category_counts.get("real_embedding", 0),
        "mock_only_count": semantics_counts.get("mocked_behavior", 0),
        "status_echo_count": semantics_counts.get("status_echo", 0),
        "fake_retriever_count": sum(1 for row in added if row.uses_fake_retriever),
        "monkeypatch_count": sum(1 for row in added if row.uses_monkeypatch),
        "tests_only_asserting_constant_status": [asdict(row) for row in added if row.asserts_status_only],
        "added_tests": [asdict(row) for row in added],
    }
    result["pass"] = (
        result["physical_added_test_functions"] >= 80
        and result["integration_count"] >= 30
        and result["security_count"] >= 15
        and result["persistence_count"] >= 10
        and result["http_count"] >= 5
        and result["real_faiss_count"] >= 10
    )
    result["status"] = "V181_TEST_DEPTH_VERIFIED" if result["pass"] else "V180_TEST_DEPTH_CLAIM_DOWNGRADED"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "physical_added": result["physical_added_test_functions"], "net_growth": result["net_test_growth"]}, ensure_ascii=False))


def _collect_current() -> list[TestFunction]:
    rows: list[TestFunction] = []
    for path in sorted((ROOT / "ai-service" / "tests").glob("test_*.py")):
        rows.extend(_parse_functions(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")))
    return rows


def _collect_baseline() -> list[TestFunction]:
    files = _git_lines(["ls-tree", "-r", "--name-only", BASELINE, "ai-service/tests"])
    rows: list[TestFunction] = []
    for path in files:
        if not path.endswith(".py"):
            continue
        try:
            source = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT, text=True, encoding="utf-8")
        except subprocess.CalledProcessError:
            continue
        rows.extend(_parse_functions(path.replace("\\", "/"), source))
    return rows


def _parse_functions(path: str, source: str) -> list[TestFunction]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rows = []
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            snippet = "\n".join(lines[node.lineno - 1 : getattr(node, "end_lineno", node.lineno)])
            rows.append(
                TestFunction(
                    path=path,
                    name=node.name,
                    line=node.lineno,
                    parametrized_cases=_parametrize_case_count(node),
                    category=_category(path, node.name, snippet),
                    semantics=_semantics(snippet),
                    uses_mock=bool(re.search(r"\b(mock|Mock|monkeypatch|patch)\b", snippet)),
                    uses_fake_retriever="Fake" in snippet or "fake" in snippet or "HashDenseRetriever" in snippet,
                    uses_monkeypatch="monkeypatch" in snippet,
                    asserts_status_only=_asserts_status_only(snippet),
                )
            )
    return rows


def _parametrize_case_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    total = 0
    for decorator in node.decorator_list:
        text = ast.unparse(decorator) if hasattr(ast, "unparse") else ""
        if "parametrize" not in text:
            continue
        for sub in ast.walk(decorator):
            if isinstance(sub, (ast.List, ast.Tuple)):
                total = max(total, len(sub.elts))
    return total


def _category(path: str, name: str, source: str) -> str:
    haystack = f"{path} {name} {source}".lower()
    if "integration_api" in name.lower():
        return "integration"
    if "persistence" in name.lower():
        return "persistence"
    if "http" in haystack or "uvicorn" in haystack or "urlopen" in haystack:
        return "http"
    if "faiss" in haystack or "indexflatip" in haystack:
        return "real_faiss"
    if "bge" in haystack or "embedding" in haystack or "encode_" in haystack:
        return "real_embedding"
    if "tenant" in haystack or "prompt_injection" in haystack or "pii" in haystack or "security" in haystack:
        return "security"
    if "restart" in haystack or "persistent" in haystack or "rollback" in haystack or "cross_process" in haystack:
        return "persistence"
    if "api" in haystack or "agent" in haystack or "retrieval" in haystack or "rag" in haystack:
        return "integration"
    return "unit"


def _semantics(source: str) -> str:
    lowered = source.lower()
    if re.search(r"return\s+[\"'].*pass", lowered):
        return "status_echo"
    if "assert" in lowered and "status" in lowered and not any(token in lowered for token in ["search(", "encode", "urlopen", "subprocess", "index.add"]):
        return "status_echo"
    if any(token in lowered for token in ["urlopen", "subprocess", "index.add", "index.search", "encode_documents", "load_active"]):
        return "integration_real"
    if any(token in lowered for token in ["monkeypatch", "mock", "hashdenseretriever"]):
        return "mocked_behavior"
    if "exists()" in lowered and "assert" in lowered:
        return "artifact_presence_only"
    return "behavioral_real"


def _asserts_status_only(source: str) -> bool:
    meaningful = ["search(", "encode", "urlopen", "subprocess", "index.add", "filter_documents", "load_active"]
    return "assert" in source and "status" in source.lower() and not any(token in source for token in meaningful)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _git_lines(args: list[str]) -> list[str]:
    output = subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")
    return [line.strip() for line in output.splitlines() if line.strip()]


if __name__ == "__main__":
    main()
