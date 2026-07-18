from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantPrincipal:
    tenant_id: str
    tenant_hash: str

    @classmethod
    def from_tenant_id(cls, tenant_id: str) -> "TenantPrincipal":
        normalized = normalize_tenant_id(tenant_id)
        return cls(tenant_id=normalized, tenant_hash=hashlib.sha256(normalized.encode()).hexdigest()[:24])


def normalize_tenant_id(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").strip().lower()
    if not normalized:
        raise ValueError("TENANT_ID_REQUIRED")
    if any(unicodedata.category(ch)[0] == "C" for ch in normalized):
        raise ValueError("TENANT_ID_INVALID")
    if any(ch in normalized for ch in ["/", "\\", "\x00", ".."]):
        raise ValueError("TENANT_ID_INVALID")
    return normalized


class TenantAccessController:
    def can_read(self, principal: TenantPrincipal, document: dict) -> bool:
        if document.get("deleted") or document.get("active") is False:
            return False
        scope = str(document.get("access_scope") or "tenant")
        if scope == "public":
            return True
        document_tenant = normalize_tenant_id(str(document.get("tenant_id") or ""))
        return document_tenant == principal.tenant_id

    def filter_documents(self, principal: TenantPrincipal, documents: list[dict]) -> list[dict]:
        return [doc for doc in documents if self.can_read(principal, doc)]

    def safe_error(self, code: str) -> dict:
        return {"error_code": code, "message": "resource not available for current tenant"}
