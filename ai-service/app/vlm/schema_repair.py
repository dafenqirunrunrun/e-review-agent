import json
import re
import time
from typing import Any

from app.vlm.schemas import VisualEvidenceResult


REQUIRED_KEYS = {
    "image_available",
    "image_quality",
    "ocr_text",
    "visual_findings",
    "package_damage_detected",
    "product_damage_detected",
    "leakage_detected",
    "missing_part_detected",
    "product_mismatch_detected",
    "privacy_risk_detected",
    "text_image_consistency",
    "visual_risk_level",
    "visual_evidence",
    "unsupported_visual_claims",
    "need_human_review",
    "missing_information",
}
ALLOWED_KEYS = set(REQUIRED_KEYS)


def parse_raw_visual_schema(raw_output: str) -> VisualEvidenceResult:
    parsed = json.loads(raw_output.strip())
    if not isinstance(parsed, dict):
        raise ValueError("JSON_OUTPUT_IS_NOT_OBJECT")
    missing = REQUIRED_KEYS - set(parsed)
    unknown = set(parsed) - ALLOWED_KEYS
    if missing:
        raise ValueError("MISSING_REQUIRED_FIELD")
    if unknown:
        raise ValueError("EXTRA_UNKNOWN_FIELD")
    return VisualEvidenceResult.model_validate(parsed)


def extract_json_object(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("NO_JSON_OBJECT_IN_OUTPUT")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("JSON_OUTPUT_IS_NOT_OBJECT")
    return parsed


def normalize_visual_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in payload.items() if key in ALLOWED_KEYS}
    normalized["image_available"] = bool(normalized.get("image_available", True))
    normalized["image_quality"] = _literal(
        normalized.get("image_quality"),
        {"clear", "blurred", "occluded", "irrelevant", "uncertain"},
        "uncertain",
    )
    normalized["ocr_text"] = _string_list(normalized.get("ocr_text"))
    normalized["visual_evidence"] = _string_list(normalized.get("visual_evidence"))
    normalized["unsupported_visual_claims"] = _string_list(normalized.get("unsupported_visual_claims"))
    normalized["missing_information"] = _string_list(normalized.get("missing_information"))
    normalized["visual_findings"] = _visual_findings(normalized.get("visual_findings"))
    normalized["text_image_consistency"] = _literal(
        normalized.get("text_image_consistency"),
        {"consistent", "conflicting", "unrelated", "uncertain"},
        "uncertain",
    )
    normalized["visual_risk_level"] = _literal(
        normalized.get("visual_risk_level"),
        {"low", "medium", "high", "uncertain"},
        "uncertain",
    )
    for key in [
        "package_damage_detected",
        "product_damage_detected",
        "leakage_detected",
        "missing_part_detected",
        "product_mismatch_detected",
        "privacy_risk_detected",
    ]:
        normalized[key] = bool(normalized.get(key, False))
    normalized["need_human_review"] = bool(normalized.get("need_human_review", True))
    return normalized


def repair_visual_schema(raw_output: str) -> dict[str, Any]:
    text = raw_output.strip()
    if not text:
        raise ValueError("EMPTY_VLM_OUTPUT")
    try:
        parsed = extract_json_object(text)
        normalized = normalize_visual_payload(parsed)
        for key, value in _default_visual_payload().items():
            normalized.setdefault(key, value)
        return normalized
    except Exception:
        repaired = _default_visual_payload()
        repaired["visual_findings"] = [
            {
                "type": "other",
                "description": "The model output was not valid JSON; visual facts were not inferred during safe repair.",
                "confidence": 0.3,
            }
        ]
        repaired["visual_risk_level"] = "medium"
        repaired["need_human_review"] = True
        repaired["missing_information"] = [
            "The real VLM output was not strict JSON; safe repair avoided inventing visual facts."
        ]
        return repaired


def parse_or_repair_visual_schema(raw_output: str) -> tuple[VisualEvidenceResult, dict[str, Any]]:
    raw_schema_valid = False
    deterministic_normalization_used = False
    deterministic_normalization_success = False
    safe_repair_used = False
    safe_repair_success = False
    repair_used = False
    repair_reason = None
    failure_reasons = classify_raw_schema_failure(raw_output)
    parse_started = time.perf_counter()
    parse_ms = 0.0
    normalization_ms = 0.0
    repair_ms = 0.0
    try:
        result = parse_raw_visual_schema(raw_output)
        raw_schema_valid = True
    except Exception as exc:
        parse_ms = round((time.perf_counter() - parse_started) * 1000, 2)
        repair_used = True
        repair_reason = type(exc).__name__
        try:
            normalization_started = time.perf_counter()
            deterministic_normalization_used = True
            payload = normalize_visual_payload(extract_json_object(_strip_markdown_fence(raw_output).strip()))
            result = VisualEvidenceResult.model_validate(payload)
            deterministic_normalization_success = True
        except Exception:
            normalization_ms = round((time.perf_counter() - normalization_started) * 1000, 2)
            repair_started = time.perf_counter()
            safe_repair_used = True
            payload = repair_visual_schema(raw_output)
            normalized = normalize_visual_payload(payload)
            result = VisualEvidenceResult.model_validate(normalized)
            safe_repair_success = True
            repair_ms = round((time.perf_counter() - repair_started) * 1000, 2)
        else:
            normalization_ms = round((time.perf_counter() - normalization_started) * 1000, 2)
    else:
        parse_ms = round((time.perf_counter() - parse_started) * 1000, 2)
    meta = {
        "raw_schema_valid": raw_schema_valid,
        "repair_used": repair_used,
        "repaired_schema_valid": True,
        "repair_reason": repair_reason,
        "raw_schema_failure_reasons": [] if raw_schema_valid else failure_reasons,
        "deterministic_normalization_used": deterministic_normalization_used,
        "deterministic_normalization_success": deterministic_normalization_success,
        "safe_repair_used": safe_repair_used,
        "safe_repair_success": safe_repair_success,
        "second_generate_count": 0,
        "parse_ms": parse_ms,
        "normalization_ms": normalization_ms,
        "repair_ms": repair_ms,
    }
    return result, meta


def classify_raw_schema_failure(raw_output: str) -> list[str]:
    text = raw_output or ""
    stripped = text.strip()
    reasons = []
    if stripped.startswith("```"):
        reasons.append("markdown_code_fence")
    if stripped and not stripped.startswith("{"):
        reasons.append("leading_explanation")
    if stripped.endswith("```"):
        reasons.append("trailing_explanation")
    if "'" in stripped and '"' not in stripped:
        reasons.append("single_quote")
    if re.search(r",\s*[}\]]", stripped):
        reasons.append("trailing_comma")
    try:
        parsed = json.loads(stripped)
    except Exception:
        reasons.append("invalid_json_syntax")
        try:
            parsed = extract_json_object(_strip_markdown_fence(stripped))
        except Exception:
            parsed = None
    if isinstance(parsed, dict):
        missing = REQUIRED_KEYS - set(parsed)
        unknown = set(parsed) - ALLOWED_KEYS
        if missing:
            reasons.append("missing_required_field")
        if unknown:
            reasons.append("extra_unknown_field")
        if any(isinstance(key, str) and re.search(r"[\u4e00-\u9fff]", key) for key in parsed):
            reasons.append("chinese_key_name")
        for key in ["ocr_text", "visual_findings", "visual_evidence", "unsupported_visual_claims", "missing_information"]:
            if parsed.get(key) is None:
                reasons.append("null_array")
                break
        for key in [
            "package_damage_detected",
            "product_damage_detected",
            "leakage_detected",
            "missing_part_detected",
            "product_mismatch_detected",
            "privacy_risk_detected",
            "need_human_review",
        ]:
            if key in parsed and not isinstance(parsed.get(key), bool):
                reasons.append("wrong_boolean_type")
                break
        if parsed.get("image_quality") not in {None, "clear", "blurred", "occluded", "irrelevant", "uncertain"}:
            reasons.append("invalid_enum")
        if parsed.get("text_image_consistency") not in {None, "consistent", "conflicting", "unrelated", "uncertain"}:
            reasons.append("invalid_enum")
        if parsed.get("visual_risk_level") not in {None, "low", "medium", "high", "uncertain"}:
            reasons.append("invalid_enum")
        for finding in parsed.get("visual_findings") or []:
            if not isinstance(finding, dict):
                reasons.append("nested_structure_mismatch")
                continue
            confidence = finding.get("confidence")
            try:
                if confidence is not None and not 0 <= float(confidence) <= 1:
                    reasons.append("confidence_out_of_range")
                    break
            except (TypeError, ValueError):
                reasons.append("confidence_out_of_range")
                break
    if not reasons:
        reasons.append("other")
    return sorted(set(reasons))


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped


def _default_visual_payload() -> dict[str, Any]:
    return {
        "image_available": True,
        "image_quality": "uncertain",
        "ocr_text": [],
        "visual_findings": [],
        "visual_evidence": [],
        "package_damage_detected": False,
        "product_damage_detected": False,
        "leakage_detected": False,
        "missing_part_detected": False,
        "product_mismatch_detected": False,
        "privacy_risk_detected": False,
        "text_image_consistency": "uncertain",
        "visual_risk_level": "uncertain",
        "need_human_review": True,
        "unsupported_visual_claims": [],
        "missing_information": [],
    }


def _literal(value: Any, allowed: set[str], default: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return default


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item)[:1000] for item in value if item is not None]
    return [str(value)[:1000]]


def _visual_findings(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    findings = []
    for item in items:
        if isinstance(item, dict):
            finding_type = _literal(
                item.get("type"),
                {
                    "package_damage",
                    "product_damage",
                    "leakage",
                    "missing_part",
                    "product_mismatch",
                    "contamination",
                    "irrelevant",
                    "other",
                },
                "other",
            )
            description = str(item.get("description") or item.get("text") or "uncertain visual finding")[:1000]
            confidence = item.get("confidence", 0.3)
        else:
            finding_type = "other"
            description = str(item)[:1000]
            confidence = 0.3
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.3
        findings.append(
            {
                "type": finding_type,
                "description": description,
                "confidence": max(0.0, min(1.0, confidence_value)),
            }
        )
    return findings
