from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DatasetAccessViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class DatasetAccessGuard:
    allowed_roles: frozenset[str] = frozenset({"train", "validation"})
    sealed_holdout_hashes: frozenset[str] = frozenset()

    def validate_row(self, row: dict[str, Any], *, context: str = "validation_only_analysis") -> None:
        metadata = row.get("metadata") or {}
        role = str(metadata.get("split") or metadata.get("role") or row.get("split") or "")
        sample_hash = str(metadata.get("sample_hash") or row.get("sample_hash") or "")
        if role == "holdout" or role.startswith("engineering_holdout"):
            raise DatasetAccessViolation(f"{context}: holdout role is not allowed")
        if role and role not in self.allowed_roles:
            raise DatasetAccessViolation(f"{context}: split role {role!r} is not allowed")
        if sample_hash and sample_hash in self.sealed_holdout_hashes:
            raise DatasetAccessViolation(f"{context}: sealed holdout sample hash is not allowed")

    def validate_rows(self, rows: list[dict[str, Any]], *, context: str = "validation_only_analysis") -> None:
        for row in rows:
            self.validate_row(row, context=context)


def guard_validation_rows(rows: list[dict[str, Any]], sealed_holdout_hashes: set[str] | None = None) -> DatasetAccessGuard:
    guard = DatasetAccessGuard(sealed_holdout_hashes=frozenset(sealed_holdout_hashes or set()))
    guard.validate_rows(rows)
    return guard
