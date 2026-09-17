from __future__ import annotations

"""Replay local review records through current routing and the shadow-only gate."""

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.agentic_workflow.workflow import IntentRouterAgent
from app.core.config import settings
from app.observability.fast_eligibility_shadow import (
    CurrentRouteSignal,
    FastEligibilityShadowEvaluator,
)
from app.schemas.review import ReviewAnalyzeRequest


DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step214_fast_eligibility_shadow"
DEFAULT_REPORT = REPO_ROOT / "docs" / "FAST_ELIGIBILITY_SHADOW_REPORT.md"
DEFAULT_POLICY = ROOT / "artifacts" / "step213h_fast_eligibility_gate" / "fast_eligibility_policy_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("mysql",), default="mysql")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser.parse_args()


def load_mysql_requests() -> tuple[list[dict], int]:
    required = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USERNAME", "MYSQL_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("MYSQL_SHADOW_REPLAY_CONFIG_MISSING:" + ",".join(missing))
    environment = dict(os.environ)
    environment["MYSQL_PWD"] = environment["MYSQL_PASSWORD"]
    query = (
        "select JSON_OBJECT("
        "'reviewId',cast(id as char),'productId',cast(value_id as char),"
        "'productName','local-comment','reviewText',coalesce(content,''),"
        "'rating',if(rating_source='USER_PROVIDED',star,null),"
        "'ratingSource',coalesce(rating_source,'UNKNOWN'),'storedRating',star) "
        "from litemall_comment where deleted=0 order by id"
    )
    command = [
        "mysql",
        "--default-character-set=utf8mb4",
        f"--host={environment['MYSQL_HOST']}",
        f"--port={environment['MYSQL_PORT']}",
        f"--user={environment['MYSQL_USERNAME']}",
        f"--database={environment['MYSQL_DATABASE']}",
        "--batch",
        "--raw",
        "--skip-column-names",
        "--execute",
        query,
    ]
    completed = subprocess.run(command, capture_output=True, check=True, env=environment)
    rows = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]
    return rows, len(rows)


def current_signal(router: IntentRouterAgent, payload: ReviewAnalyzeRequest) -> CurrentRouteSignal:
    decision = router._route_with_rules(payload)
    return CurrentRouteSignal(
        route=decision.route,
        intent=decision.intent,
        risk_hints=tuple(decision.risk_hints),
        reason_codes=tuple(decision.reason_codes),
        safety_gate_triggered="HIGH_RISK_SAFETY_GATE" in decision.reason_codes,
    )


def run(args: argparse.Namespace) -> dict:
    if settings.intent_router_provider != "rule":
        raise RuntimeError("STEP214_REPLAY_REQUIRES_CURRENT_RULE_ROUTER")
    source_rows, source_count = load_mysql_requests()
    evaluator = FastEligibilityShadowEvaluator(
        policy_path=args.policy,
        output_dir=args.output_dir,
        report_path=args.report,
    )
    evaluator.reset()
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    skipped = 0
    for row in source_rows:
        try:
            payload = ReviewAnalyzeRequest.model_validate(row)
        except Exception:
            skipped += 1
            continue
        evaluator.observe(payload, current_signal(router, payload))
    metrics = evaluator.finalize(
        {
            "mode": "mysql_read_only_request_replay",
            "sourceTable": "litemall_comment",
            "sourceRecordCount": source_count,
            "validRequestCount": source_count - skipped,
            "skippedInvalidRequestCount": skipped,
            "sourceRatingCounts": dict(sorted(Counter(str(row.get("storedRating")) for row in source_rows).items())),
            "effectiveRatingCounts": dict(sorted(Counter(str(row.get("rating")) for row in source_rows).items())),
            "ratingSourceCounts": dict(sorted(Counter(str(row.get("ratingSource")) for row in source_rows).items())),
            "ratingContractVersion": "review-rating-v2",
            "currentRouterProvider": "rule",
            "rawReviewTextPersisted": False,
        }
    )
    return metrics


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
