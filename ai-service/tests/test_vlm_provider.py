from pathlib import Path

from app.vlm.schemas import VisualEvidenceResult
from app.vlm.config import VlmConfig
from app.vlm.service import VlmService
from app.vlm.provider import LocalQwen3VlProvider
from app.vlm.qwen3_vl_runtime import Qwen3VlRuntimeResult
from app.vlm.schema_repair import parse_or_repair_visual_schema


VALID_VISUAL_JSON = """{
  "image_available": true,
  "image_quality": "clear",
  "ocr_text": [],
  "visual_findings": [{"type":"package_damage","description":"box corner dent","confidence":0.72}],
  "package_damage_detected": true,
  "product_damage_detected": false,
  "leakage_detected": false,
  "missing_part_detected": false,
  "product_mismatch_detected": false,
  "privacy_risk_detected": false,
  "text_image_consistency": "uncertain",
  "visual_risk_level": "medium",
  "visual_evidence": ["box corner dent"],
  "unsupported_visual_claims": [],
  "need_human_review": true,
  "missing_information": []
}"""


def test_visual_schema_rejects_invalid_confidence():
    result = VlmService.validate_schema({
        "image_available": True,
        "image_quality": "clear",
        "visual_findings": [{"type": "package_damage", "description": "box dent", "confidence": 1.5}],
        "text_image_consistency": "uncertain",
        "visual_risk_level": "medium",
        "need_human_review": True,
    })
    assert result["schema_valid"] is False


def test_visual_schema_accepts_uncertain_low_quality_case():
    payload = {
        "image_available": True,
        "image_quality": "blurred",
        "ocr_text": [],
        "visual_findings": [],
        "text_image_consistency": "uncertain",
        "visual_risk_level": "uncertain",
        "visual_evidence": [],
        "unsupported_visual_claims": [],
        "need_human_review": True,
        "missing_information": ["图片模糊"],
    }
    parsed = VisualEvidenceResult.model_validate(payload)
    assert parsed.image_quality == "blurred"
    assert parsed.need_human_review is True


def test_vlm_status_and_smoke_are_blocked_without_local_model(monkeypatch, tmp_path):
    service = VlmService(config=VlmConfig(model_dir=Path(tmp_path / "missing-vlm")))
    status = service.status()
    assert status.model_available is False
    assert status.blocked_reason == "VLM_MODEL_NOT_AVAILABLE"
    smoke = service.smoke_test()
    assert smoke.marker == "MULTIMODAL_VLM_EVAL_BLOCKED"


def test_vlm_consistency_uncertain_requires_human_review():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    body = {
        "review_text": "图片看不清，但用户说商品破损",
        "visual_result": {
            "image_available": True,
            "image_quality": "uncertain",
            "ocr_text": [],
            "visual_findings": [],
            "text_image_consistency": "uncertain",
            "visual_risk_level": "uncertain",
            "visual_evidence": [],
            "unsupported_visual_claims": [],
            "need_human_review": True,
            "missing_information": ["图片无法确认"],
        },
    }
    result = client.post("/api/v1/vlm/text-image/consistency", json=body).json()
    assert result["text_image_consistency"] == "uncertain"
    assert result["need_human_review"] is True


def test_provider_maps_real_runtime_result_after_schema_repair(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_text("placeholder", encoding="utf-8")
    image = tmp_path / "image.png"
    image.write_bytes(b"fake")

    def fake_run(self, request):
        return Qwen3VlRuntimeResult(
            raw_text="visible package dent; not strict json",
            real_inference=True,
            cuda_used=True,
            fallback_used=False,
            generate_executed=True,
            total_latency_ms=12.0,
            gpu_peak_memory_mb=123.0,
            gpu_memory_after_unload_mb=0.0,
        )

    monkeypatch.setattr("app.vlm.provider.Qwen3VlRuntime.run", fake_run)
    provider = LocalQwen3VlProvider(VlmConfig(model_dir=model_dir))
    result = provider.analyze_images({"image_paths": [str(image)], "review_text": "box dent", "product_name": "demo"})

    assert result.real_inference is True
    assert result.cuda_used is True
    assert result.fallback_used is False
    assert result.schema_valid is True
    assert result.repair_used is True
    assert result.gpu_peak_memory_mb == 123.0


def test_provider_does_not_load_runtime_without_image(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_text("placeholder", encoding="utf-8")
    provider = LocalQwen3VlProvider(VlmConfig(model_dir=model_dir))

    try:
        provider.analyze_images({"image_paths": []})
    except RuntimeError as exc:
        assert str(exc) == "VLM_IMAGE_MISSING"
    else:
        raise AssertionError("provider should reject missing images before runtime load")


def test_parse_raw_json_directly_valid():
    result, meta = parse_or_repair_visual_schema(VALID_VISUAL_JSON)

    assert result.image_quality == "clear"
    assert meta["raw_schema_valid"] is True
    assert meta["repair_used"] is False
    assert meta["second_generate_count"] == 0


def test_markdown_fence_is_deterministically_normalized():
    result, meta = parse_or_repair_visual_schema("```json\n" + VALID_VISUAL_JSON + "\n```")

    assert result.schema_valid is None
    assert meta["raw_schema_valid"] is False
    assert meta["deterministic_normalization_success"] is True
    assert meta["safe_repair_used"] is False
    assert "markdown_code_fence" in meta["raw_schema_failure_reasons"]


def test_leading_and_trailing_text_json_is_extracted():
    result, meta = parse_or_repair_visual_schema("Here is JSON:\n" + VALID_VISUAL_JSON + "\nDone.")

    assert result.image_available is True
    assert meta["deterministic_normalization_success"] is True
    assert "leading_explanation" in meta["raw_schema_failure_reasons"]


def test_null_arrays_are_normalized_without_second_generate():
    raw = VALID_VISUAL_JSON.replace('"ocr_text": []', '"ocr_text": null')
    result, meta = parse_or_repair_visual_schema(raw)

    assert result.ocr_text == []
    assert meta["raw_schema_valid"] is False
    assert meta["deterministic_normalization_success"] is True
    assert meta["second_generate_count"] == 0


def test_enum_and_confidence_are_normalized_safely():
    raw = VALID_VISUAL_JSON.replace('"image_quality": "clear"', '"image_quality": " CLEAR "')
    raw = raw.replace('"confidence":0.72', '"confidence":7.2')
    result, meta = parse_or_repair_visual_schema(raw)

    assert result.image_quality == "uncertain"
    assert result.visual_findings[0].confidence == 1.0
    assert "invalid_enum" in meta["raw_schema_failure_reasons"]
    assert "confidence_out_of_range" in meta["raw_schema_failure_reasons"]


def test_missing_fields_are_safely_completed_without_visual_fact_invention():
    result, meta = parse_or_repair_visual_schema('{"image_available": true, "image_quality": "clear"}')

    assert result.image_quality == "clear"
    assert result.package_damage_detected is False
    assert result.visual_findings == []
    assert meta["raw_schema_valid"] is False
    assert meta["deterministic_normalization_success"] is True
    assert meta["second_generate_count"] == 0


def test_unknown_fields_are_removed_without_using_labels_or_filename():
    result, meta = parse_or_repair_visual_schema(
        '{"image_available":true,"image_quality":"clear","filename":"damaged_box.png","gold_label":"package_damage"}'
    )

    assert result.package_damage_detected is False
    assert result.visual_findings == []
    assert "extra_unknown_field" in meta["raw_schema_failure_reasons"]


def test_safe_repair_does_not_invent_visual_facts_or_generate_again():
    result, meta = parse_or_repair_visual_schema("not json at all, label says broken package")

    assert result.package_damage_detected is False
    assert result.visual_findings[0].type == "other"
    assert "not valid JSON" in result.visual_findings[0].description
    assert meta["safe_repair_success"] is True
    assert meta["second_generate_count"] == 0
