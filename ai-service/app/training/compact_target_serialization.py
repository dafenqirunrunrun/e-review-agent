from __future__ import annotations

import json
from typing import Any

from app.contracts.e_review_decision import canonical_field_order, validate_canonical_decision


COMPACT_TARGET_SERIALIZATION_VERSION = "compact_target_v2.2.0"


def compact_canonical_serialize(decision: dict[str, Any]) -> str:
    validated = validate_canonical_decision(decision)
    payload = validated.model_dump(mode="json")
    ordered = {key: payload[key] for key in canonical_field_order()}
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
