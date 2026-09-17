import hashlib
import json
from pathlib import Path

from PIL import Image, ImageStat

from realworld_data_policy import ROOT, load_jsonl, write_json, write_jsonl


PILOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
RAW_IMAGES = PILOT / "raw-images"
PRIVATE_MANIFEST = PILOT / "manifests" / "image_private_manifest.jsonl"
PRIVATE_AUDIT = PILOT / "privacy-audit" / "image_privacy_private_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_image_privacy_audit.json"
REPORT = ROOT / "docs" / "159_v1619_pilot_image_privacy_audit.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_meta(path: Path) -> dict:
    with Image.open(path) as image:
        exif = image.getexif()
        stat = ImageStat.Stat(image.convert("L").resize((32, 32)))
        return {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "has_exif": bool(exif),
            "exif_gps": 34853 in exif,
            "alpha": "A" in image.getbands(),
            "mean_luminance": stat.mean[0],
            "std_luminance": stat.stddev[0],
        }


def decision(meta: dict, detector_failures: list[str]) -> tuple[str, list[str]]:
    risks = []
    if meta["exif_gps"]:
        risks.append("exif_gps")
    if meta["width"] < 64 or meta["height"] < 64:
        risks.append("too_small")
    if meta["std_luminance"] < 1:
        risks.append("blank_or_near_blank")
    if detector_failures:
        return "automated_uncertain", risks + [f"detector_unavailable:{name}" for name in detector_failures]
    if risks:
        return "automated_uncertain", risks
    return "automated_cleared", []


def main() -> int:
    rows = load_jsonl(PRIVATE_MANIFEST)
    private_rows = []
    public_rows = []
    counts = {"automated_cleared": 0, "automated_redacted": 0, "automated_uncertain": 0, "automated_rejected": 0}
    detector_failures = ["ocr_engine", "face_detector", "qr_barcode_detector"]
    for row in rows:
        image_id = row.get("image_id")
        path = RAW_IMAGES / f"{image_id}.jpg"
        if not path.exists():
            status = "automated_uncertain"
            risks = ["image_file_missing"]
            meta = {}
            source_hash = None
        else:
            try:
                meta = image_meta(path)
                status, risks = decision(meta, detector_failures)
                source_hash = sha256(path)
            except Exception as exc:
                status = "automated_rejected"
                risks = [type(exc).__name__]
                meta = {}
                source_hash = None
        counts[status] += 1
        private_rows.append(
            {
                "image_id": image_id,
                "source_image_hash": source_hash,
                "privacy_status": status,
                "risk_flags": risks,
                "detector_versions": {
                    "pillow": Image.__version__,
                    "ocr": "unavailable",
                    "face": "unavailable",
                    "qr_barcode": "unavailable",
                },
                "metadata": meta,
            }
        )
        public_rows.append(
            {
                "image_id_hash": hashlib.sha256(str(image_id).encode("utf-8")).hexdigest()[:24],
                "privacy_status": status,
                "risk_flag_count": len(risks),
                "detector_failure_count": len(detector_failures),
            }
        )
    write_jsonl(PRIVATE_AUDIT, private_rows)
    write_jsonl(ROOT / "data" / "real_world" / "pilot_manifest" / "image_privacy_aggregate_manifest.jsonl", public_rows)
    payload = {
        "marker": "PILOT_IMAGE_PRIVACY_AUDIT_COMPLETE",
        "image_count": len(rows),
        **counts,
        "detector_failures": detector_failures,
        "policy": "detector failure or uncertainty blocks automated_cleared",
    }
    write_json(OUT, payload)
    REPORT.write_text(
        f"""# v1.6.1.9 Pilot Image Privacy Audit

## Conclusion

`{payload['marker']}`

Automated screening is not human privacy review. OCR, face, and QR/barcode
detectors are unavailable in this environment, so images are conservatively
classified as `automated_uncertain` unless all required detector layers pass.

## Counts

- automated_cleared: {payload['automated_cleared']}
- automated_redacted: {payload['automated_redacted']}
- automated_uncertain: {payload['automated_uncertain']}
- automated_rejected: {payload['automated_rejected']}
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
