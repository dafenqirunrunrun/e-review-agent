from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-rc" / "repository-secret-scan.json"

SKIP_DIRS = {
    ".git",
    "node_modules",
    "target",
    "dist",
    "logs",
    "__pycache__",
    ".idea",
    ".vscode",
    "artifacts",
}
TEXT_SUFFIXES = {
    ".java",
    ".py",
    ".ps1",
    ".sh",
    ".yml",
    ".yaml",
    ".properties",
    ".json",
    ".md",
    ".txt",
    ".xml",
    ".js",
    ".vue",
    ".env",
    ".example",
}
ALLOWLIST_VALUES = {
    "admin123",
    "litemall123456",
    "XXXXXXXXX",
    "XXXXXXXXXXXXX",
    "xxxxxx",
    "111111",
    "test-only-key",
    "example",
    "placeholder",
}
ALLOWLIST_PATH_PARTS = {
    "doc",
    "docs",
    "deploy",
    "docker",
    "delivery",
}
PATTERNS = {
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer-token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "assigned-secret": re.compile(
        r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|accessKeySecret|secretKey)\b\s*[:=]\s*['\"]?([^'\"\s#]+)"
    ),
}


def main() -> int:
    findings = []
    scanned = 0
    for path in iter_files(ROOT):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
        rel = path.relative_to(ROOT).as_posix()
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(2) if name == "assigned-secret" else match.group(0)
                if name == "assigned-secret" and path.suffix.lower() in {".java", ".js", ".vue", ".py"}:
                    continue
                if is_allowed(rel, value):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                findings.append({"type": name, "path": rel, "line": line, "valuePreview": preview(value)})

    result = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if not findings else "FAIL",
        "scannedFiles": scanned,
        "findingCount": len(findings),
        "findings": findings[:100],
        "allowlistPolicy": {
            "placeholderValuesAllowed": sorted(ALLOWLIST_VALUES),
            "docsDeployDockerExamplesAllowed": sorted(ALLOWLIST_PATH_PARTS),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if findings:
        print("E_REVIEW_REPOSITORY_SECRET_SCAN_FAIL")
        print(json.dumps({"findingCount": len(findings), "output": str(OUT)}, ensure_ascii=False))
        return 1
    print("E_REVIEW_REPOSITORY_SECRET_SCAN_PASS")
    return 0


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & SKIP_DIRS:
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        suffixes = {suffix.lower() for suffix in path.suffixes}
        if path.suffix.lower() not in TEXT_SUFFIXES and not (suffixes & TEXT_SUFFIXES):
            continue
        yield path


def is_allowed(rel: str, value: str) -> bool:
    lowered = value.strip().strip("'\"").lower()
    if not lowered:
        return True
    if lowered in {item.lower() for item in ALLOWLIST_VALUES}:
        return True
    if lowered.startswith("${") or lowered.startswith("%"):
        return True
    if lowered.startswith("$"):
        return True
    if re.fullmatch(r"x+", lowered):
        return True
    if any(token in lowered for token in ("this.", "env.", "get", "set", "request.", "response.", "undefined", "null")):
        return True
    if any(char in lowered for char in ("(", ")", ";", ",")):
        return True
    if any(part in rel.split("/") for part in ALLOWLIST_PATH_PARTS):
        return True
    if "test" in rel.lower() and ("test" in lowered or lowered in {"admin123", "litemall"}):
        return True
    return False


def preview(value: str) -> str:
    value = value.strip().strip("'\"")
    if len(value) <= 8:
        return "***"
    return value[:3] + "***" + value[-3:]


if __name__ == "__main__":
    raise SystemExit(main())
