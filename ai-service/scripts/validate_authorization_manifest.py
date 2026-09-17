import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.data_governance.authorization_gate import evaluate_authorization  # noqa: E402


def load_manifest(path: Path):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required for YAML authorization manifests")
        return yaml.safe_load(text)
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--intended-use", default="internal_evaluation")
    parser.add_argument("--data-type", default="text")
    parser.add_argument("--current-date", default=None)
    parser.add_argument("--out", default="data/authorized_intake/audit/authorization_manifest_validation.json")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    current = date.fromisoformat(args.current_date) if args.current_date else None
    decision = evaluate_authorization(manifest, args.intended_use, args.data_type, current).to_dict()
    marker = "AUTHORIZED_DATA_MANIFEST_VALID" if decision["decision"] == "allowed" else "AUTHORIZED_DATA_MANIFEST_BLOCKED"
    result = {"marker": marker, "intended_use": args.intended_use, "data_type": args.data_type, "decision": decision}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(marker)
    return 0 if marker == "AUTHORIZED_DATA_MANIFEST_VALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
