from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "ai-service" / "tests" / "fixtures" / "privacy-detectors"


def font(size=22):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def save_clean():
    img = Image.new("RGB", (360, 240), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((70, 70, 290, 180), outline=(80, 120, 180), width=4, fill=(230, 240, 250))
    draw.polygon([(110, 70), (250, 70), (220, 40), (140, 40)], fill=(210, 225, 245), outline=(80, 120, 180))
    img.save(FIXTURE_DIR / "clean_product_like.png")


def save_text(name, lines):
    img = Image.new("RGB", (520, 260), "white")
    draw = ImageDraw.Draw(img)
    y = 40
    for line in lines:
        draw.text((30, y), line, fill="black", font=font(24))
        y += 42
    img.save(FIXTURE_DIR / name)


def save_qr_like():
    img = Image.new("RGB", (260, 260), "white")
    draw = ImageDraw.Draw(img)
    for x, y in [(20, 20), (180, 20), (20, 180)]:
        draw.rectangle((x, y, x + 60, y + 60), outline="black", width=8)
        draw.rectangle((x + 20, y + 20, x + 40, y + 40), fill="black")
    for i in range(9):
        for j in range(9):
            if (i * 3 + j * 5) % 4 == 0:
                draw.rectangle((95 + i * 8, 95 + j * 8, 101 + i * 8, 101 + j * 8), fill="black")
    img.save(FIXTURE_DIR / "qr_code.png")


def save_barcode_like():
    img = Image.new("RGB", (420, 180), "white")
    draw = ImageDraw.Draw(img)
    x = 30
    for width in [2, 4, 1, 5, 3, 2, 6, 1, 4, 3, 2, 5, 1, 3, 6, 2, 4]:
        draw.rectangle((x, 30, x + width, 140), fill="black")
        x += width + 6
    draw.text((120, 145), "TEST-0123456789", fill="black", font=font(18))
    img.save(FIXTURE_DIR / "barcode.png")


def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    save_clean()
    save_text("phone_text.png", ["SYNTHETIC TEST DATA", "Phone: 555-123-4567"])
    save_text("email_text.png", ["SYNTHETIC TEST DATA", "Email: test.person@example.test"])
    save_text("shipping_label.png", ["SYNTHETIC SHIPPING LABEL", "Name: Test Person", "Address: 123 Test Road", "Order: TEST-ORDER-0001"])
    save_qr_like()
    save_barcode_like()
    print("PRIVACY_DETECTOR_FIXTURES_READY")


if __name__ == "__main__":
    main()
