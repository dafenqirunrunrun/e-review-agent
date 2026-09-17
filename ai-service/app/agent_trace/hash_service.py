from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


class TraceHashService:
    def __init__(self, hmac_key: str, hash_key_id: str = "qualification-key-v1"):
        if not hmac_key:
            raise ValueError("hmac_key is required")
        self._hmac_key = hmac_key.encode("utf-8")
        self.hash_key_id = hash_key_id

    @staticmethod
    def canonical_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @staticmethod
    def sha256_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def hash_sensitive_text(self, value: str) -> str:
        return hmac.new(self._hmac_key, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def hash_canonical_object(self, value: Any) -> str:
        return self.sha256_text(self.canonical_json(value))

    def hash_ranked_ids(self, ids: list[str]) -> str:
        return self.hash_canonical_object({"rankedIds": list(ids)})

    def hash_unordered_ids(self, ids: list[str]) -> str:
        return self.hash_canonical_object({"unorderedIds": sorted(ids)})

    def hash_schema(self, schema: dict[str, Any]) -> str:
        return self.hash_canonical_object(schema)

    def hash_error_signature(self, category: str, error_type: str, message: str = "") -> str:
        return self.hash_canonical_object(
            {"category": category, "type": error_type, "messageHash": self.hash_sensitive_text(message)}
        )

    def hash_event(self, previous_event_hash: str, event_without_event_hash: dict[str, Any]) -> str:
        event_copy = dict(event_without_event_hash)
        event_copy.pop("eventHash", None)
        return self.sha256_text(previous_event_hash + self.canonical_json(event_copy))
