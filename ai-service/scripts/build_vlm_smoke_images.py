import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".runtime" / "vlm-smoke" / "images"
MANIFEST = ROOT / ".runtime" / "vlm-smoke" / "vlm_smoke_manifest.jsonl"


def font(size: int = 28):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def canvas(color=(248, 248, 246), size=(640, 480)):
    return Image.new("RGB", size, color)


def save(img: Image.Image, sample_id: str, title: str, expected: list[str], rows: list[dict]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{sample_id}.png"
    img.save(path)
    rows.append({
        "sample_id": sample_id,
        "source_type": "synthetic_smoke",
        "image_path": str(path),
        "title": title,
        "expected_visual_cues": expected,
        "allowed_use": ["provider_smoke", "schema_validation", "tool_observability"],
        "forbidden_use": ["real_external_eval", "sft_training", "rag_indexing", "paper_core_metric"],
    })


def draw_label(draw: ImageDraw.ImageDraw, text: str, xy=(24, 24), fill=(20, 30, 40), size=28):
    draw.text(xy, text, fill=fill, font=font(size))


def box_image(dented=False, label=None):
    img = canvas()
    draw = ImageDraw.Draw(img)
    draw.rectangle((150, 120, 490, 340), fill=(180, 132, 72), outline=(92, 62, 35), width=4)
    draw.line((150, 120, 250, 60, 590, 60, 490, 120), fill=(92, 62, 35), width=4)
    draw.line((490, 120, 590, 60, 590, 280, 490, 340), fill=(92, 62, 35), width=4)
    if dented:
        draw.polygon([(270, 175), (345, 145), (392, 205), (326, 245)], fill=(90, 58, 42))
        draw.line((270, 175, 392, 205), fill=(35, 20, 12), width=4)
    if label:
        draw_label(draw, label, (170, 250), fill=(30, 30, 30), size=30)
    return img


def build_images():
    rows = []
    img = box_image()
    save(img, "vlm-smoke-01-intact-box", "intact package box", ["clear_package", "no_visible_damage"], rows)

    img = box_image(dented=True)
    save(img, "vlm-smoke-02-dented-box", "visible dented package box", ["package_damage"], rows)

    img = box_image(label="OUTER PACKAGE DAMAGED")
    save(img, "vlm-smoke-03-package-damage-text", "test sign with package damage text", ["ocr_package_damage"], rows)

    img = box_image(dented=True).filter(ImageFilter.GaussianBlur(radius=5))
    save(img, "vlm-smoke-04-blurred", "blurred package image", ["blurred", "uncertain"], rows)

    img = canvas((230, 230, 230))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 640, 480), fill=(60, 60, 60))
    draw.ellipse((250, 170, 390, 310), fill=(220, 220, 220))
    draw_label(draw, "occluded image", (220, 32), fill=(255, 255, 255), size=30)
    save(img, "vlm-smoke-05-occluded", "large occlusion image", ["occluded", "uncertain"], rows)

    img = canvas((169, 210, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 330, 640, 480), fill=(90, 160, 90))
    draw.ellipse((450, 40, 560, 150), fill=(255, 230, 80))
    draw_label(draw, "landscape", (30, 30))
    save(img, "vlm-smoke-06-unrelated-landscape", "unrelated landscape", ["irrelevant"], rows)

    img = canvas()
    draw = ImageDraw.Draw(img)
    draw.rectangle((110, 180, 270, 340), fill=(210, 30, 30), outline=(80, 0, 0), width=4)
    draw.rectangle((370, 180, 530, 340), fill=(30, 70, 210), outline=(0, 20, 100), width=4)
    draw_label(draw, "red item vs blue item", (160, 60))
    save(img, "vlm-smoke-07-color-mismatch", "two product colors", ["product_mismatch_possible"], rows)

    img = canvas()
    draw = ImageDraw.Draw(img)
    draw.rectangle((210, 120, 430, 330), fill=(230, 230, 250), outline=(70, 70, 90), width=4)
    draw.polygon([(320, 330), (260, 430), (390, 430)], fill=(70, 140, 200))
    draw_label(draw, "liquid leakage", (215, 45))
    save(img, "vlm-smoke-08-leakage", "simple leakage diagram", ["leakage"], rows)

    img = canvas()
    draw = ImageDraw.Draw(img)
    for idx, x in enumerate([150, 260, 370]):
        if idx != 1:
            draw.rectangle((x, 180, x + 70, 250), fill=(180, 180, 180), outline=(60, 60, 60), width=3)
    draw.rectangle((260, 180, 330, 250), outline=(200, 60, 60), width=4)
    draw_label(draw, "one part missing", (205, 70))
    save(img, "vlm-smoke-09-missing-part", "missing component layout", ["missing_part"], rows)

    img = canvas()
    draw = ImageDraw.Draw(img)
    draw.rectangle((110, 120, 530, 340), fill=(245, 245, 245), outline=(50, 50, 50), width=4)
    draw_label(draw, "TEST PHONE: 13812345678", (140, 190), fill=(5, 5, 5), size=32)
    save(img, "vlm-smoke-10-privacy-phone", "synthetic privacy OCR test", ["privacy_risk", "ocr_phone"], rows)

    img = canvas((255, 255, 255))
    save(img, "vlm-smoke-11-blank", "blank white image", ["uncertain", "low_information"], rows)

    img = canvas()
    draw = ImageDraw.Draw(img)
    draw.rectangle((45, 80, 295, 400), fill=(180, 132, 72), outline=(92, 62, 35), width=3)
    draw.rectangle((345, 80, 595, 400), fill=(220, 220, 230), outline=(60, 60, 80), width=3)
    draw.polygon([(470, 250), (425, 390), (535, 390)], fill=(70, 140, 200))
    draw_label(draw, "multi-image style panel", (150, 25), size=24)
    save(img, "vlm-smoke-12-multi-panel", "combined visual cues panel", ["package", "leakage"], rows)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return rows


def main() -> int:
    rows = build_images()
    print(json.dumps({"marker": "VLM_SMOKE_IMAGES_READY", "count": len(rows), "manifest": str(MANIFEST)}, ensure_ascii=False))
    print("VLM_SMOKE_IMAGES_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
