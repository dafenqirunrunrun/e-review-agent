import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from realworld_data_policy import ROOT, load_jsonl, write_json, write_jsonl


PILOT = Path(r"D:\EReviewAgent\data-private\realworld-pilot")
RAW_IMAGES = PILOT / "raw-images"
PRIVATE_MANIFEST = PILOT / "manifests" / "image_private_manifest.jsonl"
OUT = ROOT / "data" / "real_world" / "audit" / "pilot_image_download_retry.json"
REPORT = ROOT / "docs" / "158_v1619_pilot_image_download_report.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ahash(path: Path) -> str:
    with Image.open(path) as image:
        gray = image.convert("L").resize((8, 8))
        pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def verify_image(path: Path) -> tuple[bool, str | None, str | None]:
    try:
        with Image.open(path) as image:
            fmt = image.format
            size = image.size
            image.verify()
        return True, fmt, f"{size[0]}x{size[1]}"
    except Exception as exc:
        return False, None, type(exc).__name__


def classify_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        if exc.code == 403:
            return "http_403"
        if exc.code == 404:
            return "http_404"
        if exc.code == 429:
            return "http_429"
        return f"http_{exc.code}"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, URLError):
        reason = str(exc.reason).lower()
        if "ssl" in reason or "tls" in reason:
            return "tls_failure"
        if "name" in reason or "dns" in reason:
            return "dns_failure"
        if "timed out" in reason:
            return "timeout"
    return "unknown"


def download(url: str, target: Path) -> tuple[bool, str]:
    request = Request(url, headers={"User-Agent": "EReviewAgent-PrivatePilot/1.0"})
    part = target.with_suffix(target.suffix + ".part")
    try:
        with urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            if not content_type.lower().startswith("image/"):
                return False, "invalid_content_type"
            with part.open("wb") as handle:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    handle.write(chunk)
        ok, _, _ = verify_image(part)
        if not ok:
            part.unlink(missing_ok=True)
            return False, "corrupted_image"
        part.replace(target)
        return True, "downloaded"
    except Exception as exc:
        part.unlink(missing_ok=True)
        return False, classify_error(exc)


def main() -> int:
    rows = load_jsonl(PRIVATE_MANIFEST)
    updated = []
    retried = 0
    newly_downloaded = 0
    reason_counts = {}
    for row in rows:
        item = dict(row)
        image_id = item.get("image_id")
        target = RAW_IMAGES / f"{image_id}.jpg"
        if target.exists():
            ok, fmt, size = verify_image(target)
            item.update(
                {
                    "download_status": "downloaded" if ok else "corrupted_image",
                    "valid_image": ok,
                    "format": fmt,
                    "image_size": size,
                    "sha256": sha256(target) if ok else None,
                    "perceptual_hash": ahash(target) if ok else None,
                }
            )
        elif item.get("url"):
            retried += 1
            ok, reason = download(item["url"], target)
            if ok:
                newly_downloaded += 1
            item["download_status"] = reason
            item["valid_image"] = ok
        else:
            item["download_status"] = "source_url_not_retained"
            item["valid_image"] = False
        reason_counts[item["download_status"]] = reason_counts.get(item["download_status"], 0) + 1
        updated.append(item)
        time.sleep(0.1)
    write_jsonl(PRIVATE_MANIFEST, updated)
    total_valid = sum(1 for row in updated if row.get("valid_image"))
    expected = len(updated)
    payload = {
        "marker": "PILOT_IMAGE_ACQUISITION_PARTIAL" if total_valid < expected else "PILOT_IMAGE_ACQUISITION_COMPLETE",
        "images_expected": expected,
        "images_previously_downloaded": sum(1 for row in rows if row.get("bytes")),
        "images_retried": retried,
        "images_newly_downloaded": newly_downloaded,
        "images_total_downloaded": total_valid,
        "valid_image_count": total_valid,
        "corrupted_image_count": reason_counts.get("corrupted_image", 0),
        "expired_url_count": reason_counts.get("url_expired", 0),
        "forbidden_count": reason_counts.get("http_403", 0),
        "network_failure_count": sum(reason_counts.get(k, 0) for k in ["dns_failure", "tls_failure", "timeout", "unknown"]),
        "source_url_not_retained_count": reason_counts.get("source_url_not_retained", 0),
        "final_download_success_rate": round(total_valid / expected, 4) if expected else 0.0,
        "reason_counts": reason_counts,
    }
    write_json(OUT, payload)
    REPORT.write_text(
        f"""# v1.6.1.9 Pilot Image Download Report

## Conclusion

`{payload['marker']}`

The retry step used only the existing private pilot manifest and official dataset
records already stored outside Git. No platform pages, search results, third-party
image sites, or substitute images were used.

## Metrics

- Images expected: {payload['images_expected']}
- Retried: {payload['images_retried']}
- Newly downloaded: {payload['images_newly_downloaded']}
- Total valid images: {payload['valid_image_count']}
- Final download success rate: {payload['final_download_success_rate']}
- Source URL not retained: {payload['source_url_not_retained_count']}
""",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
