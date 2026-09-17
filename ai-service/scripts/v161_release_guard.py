import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FINAL_GATE_RESULTS = ROOT / "data" / "multimodal" / "audit" / "v161_final_gate_results.json"
OUT = ROOT / "data" / "multimodal" / "audit" / "v161_release_guard_results.json"
REPORT = ROOT / "docs" / "126_v161_release_guard_report.md"
DEFAULT_TAG = "v1.6.1-realworld-multimodal-evaluation"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_result(tag: str) -> dict:
    final_gate = read_json(FINAL_GATE_RESULTS)
    final_marker = final_gate.get("marker", "MISSING")
    final_release_allowed = final_gate.get("release_allowed") is True
    final_recommended_tag = final_gate.get("recommended_tag")
    blockers = final_gate.get("release_blockers") or []

    tag_matches_gate = final_recommended_tag == tag
    release_ready = (
        final_marker == "V161_FINAL_GATE_PASS"
        and final_release_allowed
        and tag_matches_gate
    )

    return {
        "marker": "V161_RELEASE_GUARD_READY" if release_ready else "V161_RELEASE_GUARD_BLOCKED",
        "requested_tag": tag,
        "tag_command_allowed": release_ready,
        "recommended_command": f"git tag {tag}" if release_ready else None,
        "final_gate_marker": final_marker,
        "final_gate_release_allowed": final_release_allowed,
        "final_gate_recommended_tag": final_recommended_tag,
        "tag_matches_final_gate": tag_matches_gate,
        "release_blockers": blockers,
        "final_gate_evidence": "data/multimodal/audit/v161_final_gate_results.json",
    }


def report_text(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["release_blockers"]) or "- none"
    command = result["recommended_command"] or "not allowed while release guard is blocked"
    return f"""# v1.6.1 Release Guard Report

## Conclusion

`{result['marker']}`

- Requested tag: `{result['requested_tag']}`
- Tag command allowed: `{result['tag_command_allowed']}`
- Recommended command: `{command}`
- Final gate marker: `{result['final_gate_marker']}`
- Final gate release allowed: `{result['final_gate_release_allowed']}`
- Final gate recommended tag: `{result['final_gate_recommended_tag']}`
- Tag matches final gate: `{result['tag_matches_final_gate']}`

## Release Blockers

{blockers}

## Policy

This guard does not create a Git tag. It only records whether the requested release
tag is allowed by the current v1.6.1 final gate evidence. If the final gate is
blocked, the release tag must not be created.

## Evidence

- Final gate result: `{result['final_gate_evidence']}`
- Guard result: `data/multimodal/audit/v161_release_guard_results.json`
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard v1.6.1 release tag creation.")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="Release tag to validate.")
    args = parser.parse_args()

    result = build_result(args.tag)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")

    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
