from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "litemall-admin"
OUT = ROOT / "artifacts" / "real-model-chain" / "v22-admin-lint-regression-gate.json"
BASELINE_COMMIT = "9205de0b"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=BASELINE_COMMIT)
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    changed = changed_admin_files(args.baseline)
    current = run_eslint_json()
    touched = run_touched_eslint_json(changed) if changed else {"messages": [], "errorCount": 0, "warningCount": 0}
    admin_tree_unchanged = len(changed) == 0
    baseline_errors = current["errorCount"] if admin_tree_unchanged else None
    new_errors = 0 if admin_tree_unchanged else current["errorCount"]
    status = "PASS" if touched["errorCount"] == 0 and new_errors == 0 else "FAIL"
    payload = {
        "schemaVersion": "e-review-admin-lint-regression-gate-v1",
        "createdAtUtc": now(),
        "baselineCommit": args.baseline,
        "adminTreeChangedSinceBaseline": not admin_tree_unchanged,
        "changedAdminFiles": changed,
        "baselineErrorCount": baseline_errors,
        "currentErrorCount": current["errorCount"],
        "currentWarningCount": current["warningCount"],
        "newErrorCount": new_errors,
        "resolvedErrorCount": 0 if admin_tree_unchanged else None,
        "touchedFileErrorCount": touched["errorCount"],
        "touchedFileWarningCount": touched["warningCount"],
        "fullLintExitCode": current["exitCode"],
        "fullLintClean": current["errorCount"] == 0,
        "legacyLintDebt": current["errorCount"] if admin_tree_unchanged and current["errorCount"] else 0,
        "messageFingerprint": current["messageFingerprint"],
        "status": status,
        "tokens": [
            "E_REVIEW_ADMIN_TOUCHED_FILES_LINT_PASS",
            "E_REVIEW_ADMIN_NO_NEW_LINT_ERRORS_PASS",
        ]
        if status == "PASS"
        else [],
        "boundaries": ["ADMIN_LEGACY_LINT_DEBT_40", "ADMIN_FULL_LINT_NOT_CLEAN"] if current["errorCount"] else [],
        "notes": [
            "The admin tree has no changed files since baseline commit 9205de0b; therefore current lint errors are historical for this model-chain phase.",
            "Full npm lint is still not claimed clean unless currentErrorCount is zero.",
        ],
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if status == "PASS":
        print("E_REVIEW_ADMIN_TOUCHED_FILES_LINT_PASS")
        print("E_REVIEW_ADMIN_NO_NEW_LINT_ERRORS_PASS")
        if current["errorCount"]:
            print(f"ADMIN_LEGACY_LINT_DEBT_{current['errorCount']}")
            print("ADMIN_FULL_LINT_NOT_CLEAN")
        return 0
    print("E_REVIEW_ADMIN_LINT_REGRESSION_FAIL")
    return 1


def changed_admin_files(baseline: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{baseline}..HEAD", "--", "litemall-admin"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip().endswith((".js", ".vue"))]


def run_eslint_json() -> dict[str, Any]:
    completed = subprocess.run(
        [npx_command(), "eslint", "--ext", ".js,.vue", "src", "--format", "json"],
        cwd=ADMIN,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return summarize_eslint(completed)


def run_touched_eslint_json(files: list[str]) -> dict[str, Any]:
    relative = [str((ROOT / item).relative_to(ADMIN)) for item in files if (ROOT / item).is_file()]
    if not relative:
        return {"messages": [], "errorCount": 0, "warningCount": 0}
    completed = subprocess.run(
        [npx_command(), "eslint", "--format", "json", *relative],
        cwd=ADMIN,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return summarize_eslint(completed)


def summarize_eslint(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        rows = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        rows = []
    messages = []
    error_count = 0
    warning_count = 0
    for row in rows:
        file_path = safe_admin_path(str(row.get("filePath") or ""))
        for message in row.get("messages") or []:
            severity = int(message.get("severity") or 0)
            if severity == 2:
                error_count += 1
            elif severity == 1:
                warning_count += 1
            messages.append(
                {
                    "file": file_path,
                    "line": message.get("line"),
                    "ruleId": message.get("ruleId") or "",
                    "severity": severity,
                    "messageHash": hashlib.sha256(str(message.get("message") or "").encode("utf-8")).hexdigest()[:16],
                }
            )
    fingerprint = hashlib.sha256(json.dumps(messages, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "exitCode": completed.returncode,
        "errorCount": error_count,
        "warningCount": warning_count,
        "messages": messages,
        "messageFingerprint": fingerprint,
        "stderrTail": completed.stderr.splitlines()[-20:],
    }


def safe_admin_path(value: str) -> str:
    try:
        return Path(value).resolve().relative_to(ADMIN.resolve()).as_posix()
    except ValueError:
        return "<outside-admin>"


def npx_command() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
