from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.models import utc_now
from app.policy_rag.sources import REAL_POLICY_SOURCES, PolicySourceSpec
from app.rag.document_contract import stable_hash


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch public policy sources into local raw files.")
    parser.add_argument("--raw-dir", default="data/policy_rag_real/raw")
    parser.add_argument("--sources-json", default="data/policy_rag_real/sources.json")
    parser.add_argument("--failures-json", default="data/policy_rag_real/sources_failures.json")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--source-id", action="append", dest="source_ids", help="Fetch only a source id; repeatable.")
    parser.add_argument("--append", action="store_true", help="Merge selected fetches into the existing source manifests.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    selected_specs = _select_sources(args.source_ids)
    successes = []
    failures = []
    for spec in selected_specs:
        target = raw_dir / spec.fileName
        try:
            fetch_url = spec.fetchUrl or spec.sourceUrl
            body, content_type = _fetch(fetch_url, timeout=args.timeout)
            target.write_bytes(body)
            successes.append(
                _source_manifest(spec, target=target, fetch_url=fetch_url, content_type=content_type, body=body)
            )
        except Exception as exc:
            failures.append({"sourceId": spec.sourceId, "sourceUrl": spec.sourceUrl, "fetchUrl": spec.fetchUrl or spec.sourceUrl, "error": str(exc)[:300]})

    sources_path = Path(args.sources_json)
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    failures_path = Path(args.failures_json)
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    selected_ids = {spec.sourceId for spec in selected_specs}
    existing_sources = _read_manifest(sources_path) if args.append else []
    existing_failures = _read_manifest(failures_path) if args.append else []
    output_sources = _replace_selected(existing_sources, successes, selected_ids)
    output_failures = _replace_selected(existing_failures, failures, selected_ids)
    sources_path.write_text(json.dumps(output_sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    failures_path.write_text(json.dumps(output_failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = {
        "status": "pass" if successes else "fail",
        "fetchedAt": utc_now(),
        "requestedSourceCount": len(selected_specs),
        "successCount": len(successes),
        "failureCount": len(failures),
        "totalSourceCount": len(output_sources),
        "sourcesJson": str(sources_path),
        "failuresJson": str(failures_path),
        "rawDir": str(raw_dir),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if successes else 1


def _select_sources(source_ids: list[str] | None) -> list[PolicySourceSpec]:
    if not source_ids:
        return list(REAL_POLICY_SOURCES)
    by_id = {spec.sourceId: spec for spec in REAL_POLICY_SOURCES}
    missing = sorted({source_id for source_id in source_ids if source_id not in by_id})
    if missing:
        raise SystemExit("POLICY_SOURCE_ID_UNKNOWN:" + ",".join(missing))
    return [by_id[source_id] for source_id in dict.fromkeys(source_ids)]


def _source_manifest(
    spec: PolicySourceSpec,
    *,
    target: Path,
    fetch_url: str,
    content_type: str,
    body: bytes,
) -> dict[str, str]:
    return {
        "sourceId": spec.sourceId,
        "sourceUrl": spec.sourceUrl,
        "sourceName": spec.sourceName,
        "sourceType": spec.sourceType,
        "jurisdiction": spec.jurisdiction,
        "language": spec.language,
        "licenseClass": spec.licenseClass,
        "path": str(target),
        "fetchUrl": fetch_url,
        "fetchedAt": utc_now(),
        "httpContentType": content_type,
        "rawContentHash": stable_hash(body),
    }


def _read_manifest(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return content if isinstance(content, list) else []


def _replace_selected(
    existing: list[dict[str, object]],
    replacements: list[dict[str, str]],
    selected_ids: set[str],
) -> list[dict[str, object]]:
    retained = [item for item in existing if item.get("sourceId") not in selected_ids]
    return [*retained, *replacements]


def _fetch(url: str, *, timeout: int) -> tuple[bytes, str]:
    import requests

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "EReviewPolicyRAG/0.1 (+local demo)",
                "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf,text/plain,*/*;q=0.8",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.content
        content_type = response.headers.get("content-type", "")
    except requests.RequestException as exc:
        body, content_type = _fetch_with_curl(url, timeout=timeout, original_error=exc)
    if not body:
        raise RuntimeError("EMPTY_SOURCE_BODY")
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix != ".pdf" and "pdf" not in content_type.lower():
        body = _decode_text(body, response.encoding, getattr(response, "apparent_encoding", None)).encode("utf-8")
    return body, content_type


def _fetch_with_curl(url: str, *, timeout: int, original_error: Exception) -> tuple[bytes, str]:
    executable = shutil.which("curl") or shutil.which("curl.exe")
    if not executable:
        raise original_error
    with tempfile.TemporaryDirectory(prefix="e-review-policy-fetch-") as directory:
        target = Path(directory) / "source.bin"
        completed = subprocess.run(
            [
                executable,
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--max-time",
                str(timeout),
                "--output",
                str(target),
                "--write-out",
                "%{content_type}",
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not target.exists():
            detail = completed.stderr.strip() or completed.stdout.strip() or "CURL_FETCH_FAILED"
            raise RuntimeError(f"REQUESTS_FAILED:{original_error}; CURL_FAILED:{detail[:300]}") from original_error
        return target.read_bytes(), completed.stdout.strip()


def _decode_text(body: bytes, encoding: str | None, apparent_encoding: str | None) -> str:
    for candidate in ["utf-8", "utf-8-sig", "gb18030", "big5", apparent_encoding, encoding]:
        if not candidate:
            continue
        try:
            return body.decode(candidate, errors="strict")
        except Exception:
            continue
    return body.decode("utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
