from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated document parser worker")
    parser.add_argument("--parser", choices=["docling", "mineru"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.is_file():
        print("DOCUMENT_FILE_NOT_FOUND", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.bundle_dir.mkdir(parents=True, exist_ok=True)
    try:
        if args.parser == "docling":
            payload = _parse_docling(args.input, args.bundle_dir)
        else:
            payload = _parse_mineru(args.input, args.bundle_dir)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _parse_docling(path: Path, bundle_dir: Path) -> dict[str, Any]:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise RuntimeError("DOCLING_IMPORT_FAILED") from exc

    if path.suffix.lower() == ".pdf":
        pdf_options = PdfPipelineOptions()
        pdf_options.generate_picture_images = True
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
        )
    else:
        converter = DocumentConverter()
    result = converter.convert(path)
    document = result.document
    markdown = document.export_to_markdown()
    elements: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    section_path: list[str] = []
    root_title = ""

    for order, item_level in enumerate(document.iterate_items()):
        item, level = item_level
        label = _enum_value(getattr(item, "label", type(item).__name__))
        node_type = _promote_first_heading(_docling_type(label), order=order)
        text = str(getattr(item, "text", "") or "")
        if node_type == "table":
            text = _safe_table_markdown(item, document) or text
        if node_type == "title" and text:
            root_title = root_title or text.strip()
            section_path = [root_title]
        elif node_type == "section" and text:
            depth = max(1, int(level or 1))
            root_path = [root_title] if root_title else []
            body_path = section_path[len(root_path) :]
            section_path = root_path + body_path[: depth - 1] + [text.strip()]

        provenance = list(getattr(item, "prov", []) or [])
        first_prov = provenance[0] if provenance else None
        page_number = _positive_int(getattr(first_prov, "page_no", None))
        bbox = _docling_bbox(getattr(first_prov, "bbox", None))
        source_ref = str(getattr(item, "self_ref", f"docling:{order}"))
        asset_refs: list[str] = []

        if node_type == "figure":
            asset = _save_docling_picture(item, document, bundle_dir, order, page_number)
            if asset:
                assets.append(asset)
                asset_refs.append(asset["sourceRef"])
        elements.append(
            {
                "type": node_type,
                "text": text,
                "sectionPath": list(section_path),
                "pageNumber": page_number,
                "bbox": bbox,
                "assetRefs": asset_refs,
                "confidence": _docling_confidence(first_prov),
                "sourceRef": source_ref,
                "metadata": {"doclingLabel": label, "hierarchyLevel": level},
            }
        )

    extraction_warnings: list[str] = []
    if path.suffix.lower() == ".pdf":
        embedded_assets, embedded_elements, extraction_warnings = _extract_embedded_pdf_images(
            path,
            bundle_dir,
            existing_assets=assets,
            elements=elements,
        )
        assets.extend(embedded_assets)
        elements.extend(embedded_elements)

    status = _enum_value(getattr(result, "status", "unknown"))
    warnings = [] if status.lower() in {"success", "partial_success"} else [f"DOCLING_STATUS_{status.upper()}"]
    warnings.extend(extraction_warnings)
    return {
        "parser": "docling",
        "parserVersion": _package_version("docling"),
        "markdown": markdown,
        "elements": elements,
        "assets": assets,
        "warnings": warnings,
        "metadata": {"conversionStatus": status, "elementCount": len(elements), "assetCount": len(assets)},
    }


def _extract_embedded_pdf_images(
    path: Path,
    bundle_dir: Path,
    *,
    existing_assets: list[dict[str, Any]],
    elements: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], [], ["PDF_EMBEDDED_IMAGE_EXTRACTOR_UNAVAILABLE"]

    existing_hashes = {
        hashlib.sha256(candidate.read_bytes()).hexdigest()
        for asset in existing_assets
        if (candidate := bundle_dir / str(asset.get("relativePath", ""))).is_file()
    }
    assets: list[dict[str, Any]] = []
    figure_elements: list[dict[str, Any]] = []
    try:
        reader = PdfReader(path, strict=False)
        pages = list(reader.pages)
    except Exception as exc:
        return [], [], [f"PDF_EMBEDDED_IMAGE_EXTRACTION_FAILED:{type(exc).__name__}"]

    for page_number, page in enumerate(pages, start=1):
        try:
            images = list(page.images)
        except Exception:
            continue
        for image_index, image_file in enumerate(images, start=1):
            try:
                content = bytes(image_file.data)
                width, height = image_file.image.size
            except Exception:
                continue
            if not content or width < 64 or height < 64:
                continue
            content_hash = hashlib.sha256(content).hexdigest()
            if content_hash in existing_hashes:
                continue
            suffix = Path(str(getattr(image_file, "name", ""))).suffix.lower()
            target = bundle_dir / f"pdf-embedded-page-{page_number}-{image_index}{suffix or '.png'}"
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
                target.write_bytes(content)
            else:
                target = target.with_suffix(".png")
                image_file.image.save(target, format="PNG")
                content = target.read_bytes()
                content_hash = hashlib.sha256(content).hexdigest()
            source_ref = f"pdf:embedded-image:page-{page_number}:item-{image_index}"
            relative_path = target.name
            assets.append(
                {
                    "sourceRef": source_ref,
                    "kind": "image",
                    "mediaType": _media_type(relative_path),
                    "relativePath": relative_path,
                    "pageNumber": page_number,
                    "caption": f"Embedded image on page {page_number}",
                    "ocrText": "",
                    "knowledgeBearing": True,
                    "metadata": {
                        "extractionSource": "pypdf",
                        "width": width,
                        "height": height,
                        "contentHash": content_hash,
                    },
                }
            )
            figure_elements.append(
                {
                    "type": "figure",
                    "text": "",
                    "sectionPath": _last_section_path_on_page(elements, page_number),
                    "pageNumber": page_number,
                    "bbox": None,
                    "assetRefs": [source_ref],
                    "sourceRef": source_ref,
                    "metadata": {
                        "extractionSource": "pypdf",
                        "width": width,
                        "height": height,
                    },
                }
            )
            existing_hashes.add(content_hash)
    return assets, figure_elements, []


def _last_section_path_on_page(elements: list[dict[str, Any]], page_number: int) -> list[str]:
    candidates = [
        [str(part) for part in item.get("sectionPath", []) if str(part).strip()]
        for item in elements
        if item.get("pageNumber") == page_number and item.get("sectionPath")
    ]
    return candidates[-1] if candidates else []


def _parse_mineru(path: Path, bundle_dir: Path) -> dict[str, Any]:
    adjacent_cli = Path(sys.executable).with_name("mineru.exe" if sys.platform == "win32" else "mineru")
    executable = str(adjacent_cli) if adjacent_cli.is_file() else shutil.which("mineru")
    if not executable:
        raise RuntimeError("MINERU_CLI_UNAVAILABLE")
    parse_root = bundle_dir / "mineru-output"
    parse_root.mkdir(parents=True, exist_ok=True)
    backend = os.getenv("E_REVIEW_MINERU_BACKEND", "pipeline").strip() or "pipeline"
    method = os.getenv("E_REVIEW_MINERU_METHOD", "auto").strip() or "auto"
    worker_env = os.environ.copy()
    for key in ("NO_PROXY", "no_proxy"):
        existing = worker_env.get(key, "")
        entries = [item.strip() for item in existing.split(",") if item.strip()]
        for host in ("127.0.0.1", "localhost"):
            if host not in entries:
                entries.append(host)
        worker_env[key] = ",".join(entries)
    completed = subprocess.run(
        [
            executable,
            "-p",
            str(path),
            "-o",
            str(parse_root),
            "-b",
            backend,
            "-m",
            method,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=worker_env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "MINERU_PARSE_FAILED").strip()[-1600:]
        raise RuntimeError(detail)

    markdown_candidates = sorted(parse_root.rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    content_candidates = sorted(
        parse_root.rglob("*content_list.json"), key=lambda item: item.stat().st_mtime, reverse=True
    )
    if not markdown_candidates:
        raise RuntimeError("MINERU_MARKDOWN_MISSING")
    markdown_path = markdown_candidates[0]
    markdown = markdown_path.read_text(encoding="utf-8-sig", errors="replace")
    content_list: list[dict[str, Any]] = []
    if content_candidates:
        raw_content = json.loads(content_candidates[0].read_text(encoding="utf-8"))
        if isinstance(raw_content, list):
            content_list = _order_mineru_content(
                [item for item in raw_content if isinstance(item, dict)]
            )

    elements: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    section_path: list[str] = []
    root_title = ""
    for order, item in enumerate(content_list):
        raw_type = str(item.get("type", "text"))
        node_type = _mineru_type(raw_type, is_document_start=order == 0)
        if raw_type.lower() == "text" and item.get("text_level") is not None:
            node_type = _promote_first_heading("section", order=order)
        text = str(
            item.get("text")
            or item.get("table_body")
            or item.get("latex")
            or item.get("content")
            or ""
        )
        if node_type == "title" and text:
            root_title = root_title or text.strip()
            section_path = [root_title]
        elif node_type == "section" and text:
            level = max(1, _positive_int(item.get("text_level")) or 1)
            root_path = [root_title] if root_title else []
            body_path = section_path[len(root_path) :]
            section_path = root_path + body_path[: level - 1] + [text.strip()]
        page_number = (_positive_int(item.get("page_idx")) or 0) + 1
        source_ref = f"mineru:page-{page_number}:item-{order}"
        asset_refs: list[str] = []
        image_path = str(item.get("img_path") or item.get("image_path") or "")
        if image_path:
            copied = _copy_mineru_asset(markdown_path.parent, image_path, bundle_dir, order)
            if copied:
                assets.append(
                    {
                        "sourceRef": copied[0],
                        "kind": "image" if node_type != "table" else "chart",
                        "mediaType": _media_type(copied[1]),
                        "relativePath": copied[1],
                        "pageNumber": page_number,
                        "caption": _mineru_caption(item),
                        "ocrText": text,
                        "knowledgeBearing": True,
                        "metadata": {"mineruType": raw_type},
                    }
                )
                asset_refs.append(copied[0])
        elements.append(
            {
                "type": node_type,
                "text": text,
                "sectionPath": list(section_path),
                "pageNumber": page_number,
                "bbox": _mineru_bbox(item.get("bbox")),
                "assetRefs": asset_refs,
                "sourceRef": source_ref,
                "metadata": {"mineruType": raw_type},
            }
        )

    if root_title and root_title.casefold() not in markdown.casefold():
        markdown = f"# {root_title}\n\n{markdown}".strip()

    return {
        "parser": "mineru",
        "parserVersion": _package_version("mineru"),
        "markdown": markdown,
        "elements": elements,
        "assets": assets,
        "warnings": [] if content_list else ["MINERU_CONTENT_LIST_MISSING"],
        "metadata": {
            "elementCount": len(elements),
            "assetCount": len(assets),
            "contentListAvailable": bool(content_list),
            "backend": backend,
            "method": method,
        },
    }


def _save_docling_picture(
    item: Any,
    document: Any,
    bundle_dir: Path,
    order: int,
    page_number: int | None,
) -> dict[str, Any] | None:
    try:
        image = item.get_image(document)
    except Exception:
        return None
    if image is None:
        return None
    relative = f"docling-picture-{order}.png"
    image.save(bundle_dir / relative, format="PNG")
    caption = ""
    try:
        caption = str(item.caption_text(document) or "")
    except Exception:
        pass
    return {
        "sourceRef": f"docling:picture:{order}",
        "kind": "image",
        "mediaType": "image/png",
        "relativePath": relative,
        "pageNumber": page_number,
        "caption": caption,
        "ocrText": "",
        "knowledgeBearing": True,
        "metadata": {},
    }


def _safe_table_markdown(item: Any, document: Any) -> str:
    for method_name in ("export_to_markdown", "export_to_html"):
        method = getattr(item, method_name, None)
        if callable(method):
            try:
                return str(method(document) or "")
            except Exception:
                continue
    return ""


def _docling_bbox(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    values = {name: getattr(raw, name, None) for name in ("l", "t", "r", "b")}
    if not all(isinstance(item, (int, float)) for item in values.values()):
        return None
    origin = _enum_value(getattr(raw, "coord_origin", "bottom-left")).lower().replace("_", "-")
    return {
        "left": values["l"],
        "top": values["t"],
        "right": values["r"],
        "bottom": values["b"],
        "coordinateSystem": "top-left" if "top" in origin else "bottom-left",
    }


def _mineru_bbox(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        left, top, right, bottom = [float(item) for item in raw]
    except (TypeError, ValueError):
        return None
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "coordinateSystem": "top-left",
    }


def _docling_confidence(provenance: Any) -> float | None:
    if provenance is None:
        return None
    value = getattr(provenance, "confidence", None)
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _copy_mineru_asset(base: Path, raw_path: str, bundle_dir: Path, order: int) -> tuple[str, str] | None:
    source = (base / raw_path).resolve()
    if not source.is_file():
        return None
    relative = f"mineru-asset-{order}{source.suffix.lower()}"
    shutil.copy2(source, bundle_dir / relative)
    return f"mineru:asset:{order}", relative


def _mineru_caption(item: dict[str, Any]) -> str:
    value = item.get("image_caption") or item.get("table_caption") or item.get("caption") or ""
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value)


def _docling_type(label: str) -> str:
    normalized = label.lower().replace("-", "_")
    if normalized in {"title", "document_title"}:
        return "title"
    if normalized in {"section_header", "heading", "subtitle"}:
        return "section"
    if "table" in normalized:
        return "table"
    if normalized in {"picture", "figure", "chart"}:
        return "figure"
    if "caption" in normalized:
        return "caption"
    if normalized in {"formula", "equation"}:
        return "formula"
    if normalized in {"list_item", "checkbox"}:
        return "list_item"
    if normalized == "code":
        return "code"
    return "paragraph"


def _mineru_type(raw_type: str, *, is_document_start: bool = False) -> str:
    normalized = raw_type.lower().replace("-", "_")
    if normalized == "title":
        return "title"
    if normalized == "header":
        return "title" if is_document_start else "paragraph"
    if normalized == "heading":
        return "title" if is_document_start else "section"
    if normalized in {"section", "section_header"}:
        return "section"
    if "table" in normalized:
        return "table"
    if normalized in {"image", "figure", "chart"}:
        return "figure"
    if normalized in {"equation", "interline_equation", "formula"}:
        return "formula"
    if normalized in {"list", "list_item"}:
        return "list_item"
    return "paragraph"


def _promote_first_heading(node_type: str, *, order: int) -> str:
    return "title" if order == 0 and node_type == "section" else node_type


def _order_mineru_content(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = list(enumerate(rows))

    def key(item: tuple[int, dict[str, Any]]) -> tuple[int, float, float, int]:
        original_index, row = item
        page_index = _non_negative_int(row.get("page_idx"))
        bbox = row.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                left, top = float(bbox[0]), float(bbox[1])
            except (TypeError, ValueError):
                left, top = float("inf"), float("inf")
        else:
            left, top = float("inf"), float("inf")
        return page_index, top, left, original_index

    return [row for _, row in sorted(indexed, key=key)]


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _media_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suffix, "application/octet-stream")


if __name__ == "__main__":
    raise SystemExit(main())
