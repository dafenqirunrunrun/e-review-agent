from __future__ import annotations

"""Download only the public raw sources used by the Step 21.2.2A demo subset."""

import hashlib
import json
import shutil
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import certifi


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "external_raw"
ARTIFACT = ROOT / "artifacts" / "step2122a" / "source_download_manifest.json"
SOURCES = {
    "asap_chinese_reviews": {
        "url": "https://codeload.github.com/Meituan-Dianping/ASAP/zip/refs/heads/master",
        "archive": RAW / "asap" / "asap-master.zip",
        "output": RAW / "asap" / "train.csv",
        "member": "asap-master/data/train.csv",
    },
    "hf_fake_reviews_apache": {
        "url": "https://huggingface.co/datasets/theArijitDas/Fake-Reviews-Dataset/resolve/cffa887a877db747e540f15eb891f0d18070b994/data/train-00000-of-00001.parquet",
        "output": RAW / "hf_fake_reviews" / "train.parquet",
    },
    "figshare_chinese_negative_reviews": {
        "url": "https://ndownloader.figshare.com/files/24701156",
        "output": RAW / "figshare_chinese_negative" / "openData.zip",
        "expectedSize": 113648478,
        "expectedMd5": "dc3d003fd24feb3b4fa6194c5c39812d",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, output: Path, *, expected_size: int | None = None, expected_md5: str | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    context = ssl.create_default_context(cafile=certifi.where())
    for attempt in range(3):
        request = urllib.request.Request(url, headers={"User-Agent": "E-Review-Agent-Demo-Dataset/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=180, context=context) as response, temporary.open("wb") as handle:
                shutil.copyfileobj(response, handle, length=1024 * 1024)
            if expected_size is not None and temporary.stat().st_size != expected_size:
                raise IOError(f"DOWNLOAD_SIZE_MISMATCH expected={expected_size} actual={temporary.stat().st_size}")
            if expected_md5 is not None and md5(temporary) != expected_md5.lower():
                raise IOError("DOWNLOAD_MD5_MISMATCH")
            temporary.replace(output)
            return
        except (OSError, urllib.error.URLError):
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def main() -> int:
    records = []
    for source_id, source in SOURCES.items():
        output = source["output"]
        if output.exists() and (
            source.get("expectedSize") is not None and output.stat().st_size != source["expectedSize"]
            or source.get("expectedMd5") is not None and md5(output) != source["expectedMd5"].lower()
        ):
            output.unlink()
        if not output.exists():
            if "archive" in source:
                archive = source["archive"]
                if not archive.exists():
                    download(source["url"], archive)
                with zipfile.ZipFile(archive) as bundle, bundle.open(source["member"]) as reader, output.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
            else:
                download(
                    source["url"], output,
                    expected_size=source.get("expectedSize"), expected_md5=source.get("expectedMd5"),
                )
        records.append({
            "sourceId": source_id,
            "downloadMethod": "pinned_https",
            "downloadUrl": source["url"],
            "rawFile": str(output.relative_to(ROOT)).replace("\\", "/"),
            "sizeBytes": output.stat().st_size,
            "contentHash": sha256(output),
        })
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({"sources": records}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"downloaded": len(records), "manifest": str(ARTIFACT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
