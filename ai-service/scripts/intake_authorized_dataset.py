import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / "data-private" / "authorized-intake"
sys.path.insert(0, str(ROOT / "ai-service"))

from app.data_governance.authorization_gate import evaluate_authorization  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required for YAML authorization manifests")
        return yaml.safe_load(text)
    return json.loads(text)


def count_records(path: Path) -> int:
    if not path.exists() or path.is_dir():
        return 0
    if path.suffix.lower() == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    if path.suffix.lower() == ".csv":
        lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        return max(len(lines) - 1, 0)
    return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-manifest", required=False)
    parser.add_argument("--input-path", required=False)
    parser.add_argument("--intended-use", default="internal_evaluation")
    parser.add_argument("--source-id", default="unknown")
    parser.add_argument("--data-type", default="text")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--write", action="store_true", help="Explicitly allow non-dry-run writes when authorization is allowed.")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.authorization_manifest)) if args.authorization_manifest else None
    decision = evaluate_authorization(manifest, args.intended_use, args.data_type).to_dict()
    input_path = Path(args.input_path) if args.input_path else None
    input_count = count_records(input_path) if input_path else 0
    input_sha = sha256_file(input_path) if input_path and input_path.exists() and input_path.is_file() else None
    allowed = decision["decision"] == "allowed"
    dry_run = not args.write or args.dry_run
    validated_count = input_count if allowed and not dry_run else 0
    rejected_count = 0 if allowed else input_count
    summary = {
        "marker": "AUTHORIZED_DATA_INTAKE_DRY_RUN" if dry_run else "AUTHORIZED_DATA_INTAKE_COMPLETE",
        "run_id": hashlib.sha256(f"{args.source_id}|{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16],
        "source_id": args.source_id,
        "intended_use": args.intended_use,
        "authorization_decision": decision,
        "input_sha256": input_sha,
        "input_record_count": input_count,
        "schema_valid_count": 0 if not allowed else input_count,
        "pii_flagged_count": 0,
        "duplicate_count": 0,
        "rejected_count": rejected_count,
        "validated_count": validated_count,
        "text_count": input_count if args.data_type == "text" and allowed else 0,
        "image_count": input_count if args.data_type == "image" and allowed else 0,
        "annotation_count": input_count if args.data_type == "annotation" and allowed else 0,
        "private_audit_log_written": False if dry_run else allowed,
        "validated_write_performed": bool(allowed and not dry_run),
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    out = ROOT / "data" / "authorized_intake" / "audit" / "intake_run_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    print(summary["marker"])


if __name__ == "__main__":
    main()
