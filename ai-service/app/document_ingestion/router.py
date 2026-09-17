from __future__ import annotations

import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Iterable

from app.document_ingestion.adapters import (
    DocumentParserAdapter,
    LightweightDocumentAdapter,
    PdfTextDocumentAdapter,
    SpreadsheetDocumentAdapter,
    configured_external_adapter,
)
from app.document_ingestion.exceptions import DocumentIngestionError, DocumentParseError, ParserUnavailableError
from app.document_ingestion.models import DocumentFormat, DocumentProbe, NormalizedDocument, ParserAttempt, ParserKind, ParserRoute


FORMAT_BY_SUFFIX: dict[str, DocumentFormat] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".csv": "csv",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
    ".webp": "image",
}


class DocumentParserRouter:
    """Selects a parser without leaking heavy dependencies into API runtime."""

    def __init__(self, adapters: Iterable[DocumentParserAdapter] | None = None):
        if adapters is None:
            worker = Path(__file__).resolve().parents[2] / "scripts" / "document_parser_worker.py"
            adapters = [
                LightweightDocumentAdapter(),
                SpreadsheetDocumentAdapter(),
                PdfTextDocumentAdapter(),
                configured_external_adapter("docling", worker),
                configured_external_adapter("mineru", worker),
            ]
        self.adapters = {adapter.kind: adapter for adapter in adapters}

    def probe(self, path: str | Path) -> DocumentProbe:
        resolved = Path(path)
        if not resolved.is_file():
            raise DocumentParseError("DOCUMENT_FILE_NOT_FOUND", str(resolved))
        document_format = FORMAT_BY_SUFFIX.get(resolved.suffix.lower(), "unknown")
        mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        base = DocumentProbe(
            format=document_format,
            mimeType=mime_type,
            sizeBytes=resolved.stat().st_size,
            requiresOcr=document_format == "image",
            hasTextLayer=False if document_format == "image" else None,
            imageCoverageRatio=1.0 if document_format == "image" else None,
            hasKnowledgeImages=document_format == "image",
        )
        if document_format == "pdf":
            return self._probe_pdf(resolved, base)
        return base

    @staticmethod
    def _probe_pdf(path: Path, base: DocumentProbe) -> DocumentProbe:
        try:
            from pypdf import PdfReader
        except ImportError:
            return base
        try:
            reader = PdfReader(path, strict=False)
            page_limit = max(1, int(os.getenv("E_REVIEW_DOCUMENT_PROBE_PAGES", "3")))
            pages = list(reader.pages[:page_limit])
            extracted_chars = 0
            image_count = 0
            for page in pages:
                extracted_chars += len(re.sub(r"\s+", "", page.extract_text() or ""))
                try:
                    image_count += len(page.images)
                except Exception:
                    pass
        except Exception:
            return base
        if not pages:
            return base
        has_text_layer = extracted_chars >= max(20, len(pages) * 10)
        requires_ocr = not has_text_layer
        image_coverage = 1.0 if requires_ocr and image_count else min(1.0, image_count / max(1, len(pages)) * 0.2)
        return base.model_copy(
            update={
                "hasTextLayer": has_text_layer,
                "requiresOcr": requires_ocr,
                "imageCoverageRatio": image_coverage,
                "hasKnowledgeImages": image_count >= max(2, len(pages)),
            }
        )

    @staticmethod
    def select_route(probe: DocumentProbe) -> ParserRoute:
        if probe.format in {"html", "markdown", "text", "csv"}:
            return ParserRoute(primary="lightweight", reasonCodes=["TEXT_STRUCTURE_NATIVE"])
        if probe.format == "xlsx":
            return ParserRoute(
                primary="spreadsheet_native",
                fallbacks=["docling"],
                reasonCodes=["SPREADSHEET_CELL_GRAPH_REQUIRED"],
                heavy=False,
            )
        if probe.format in {"docx", "pptx"}:
            return ParserRoute(
                primary="docling",
                fallbacks=["mineru"],
                reasonCodes=["OFFICE_LAYOUT_REQUIRED"],
                heavy=True,
            )
        if probe.format == "image":
            return ParserRoute(
                primary="mineru",
                fallbacks=["docling"],
                reasonCodes=["IMAGE_OCR_REQUIRED"],
                heavy=True,
                requiresGpuLease=True,
            )
        if probe.format == "pdf":
            complex_pdf = bool(
                probe.requiresOcr
                or probe.hasTextLayer is False
                or (probe.imageCoverageRatio or 0.0) >= 0.35
                or probe.hasMultiColumnLayout
                or probe.tableCountHint >= 3
                or probe.hasKnowledgeImages
            )
            if complex_pdf:
                return ParserRoute(
                    primary="mineru",
                    fallbacks=["docling"],
                    reasonCodes=["PDF_LAYOUT_OCR_COMPLEX"],
                    heavy=True,
                    requiresGpuLease=True,
                )
            return ParserRoute(
                primary="pdf_text",
                fallbacks=["docling", "mineru"],
                reasonCodes=["PDF_TEXT_FAST_PATH"],
                heavy=False,
            )
        raise DocumentParseError("DOCUMENT_FORMAT_UNSUPPORTED", probe.format)

    def parse(
        self,
        path: str | Path,
        *,
        document_id: str,
        source_name: str | None = None,
        source_type: str = "uploaded_document",
        source_uri: str = "",
        language: str = "und",
        probe: DocumentProbe | None = None,
    ) -> NormalizedDocument:
        resolved = Path(path).resolve()
        resolved_probe = probe or self.probe(resolved)
        route = self.select_route(resolved_probe)
        attempts: list[ParserAttempt] = []

        for parser_kind in route.chain:
            adapter = self.adapters.get(parser_kind)
            if adapter is None or not adapter.available():
                attempts.append(
                    ParserAttempt(parser=parser_kind, status="unavailable", reasonCode=f"{parser_kind.upper()}_UNAVAILABLE")
                )
                continue
            started = time.perf_counter()
            try:
                result = adapter.parse(
                    resolved,
                    probe=resolved_probe,
                    document_id=document_id,
                    source_name=source_name or resolved.stem,
                    source_type=source_type,
                    source_uri=source_uri or resolved.as_uri(),
                    language=language,
                )
            except ParserUnavailableError as exc:
                attempts.append(
                    ParserAttempt(
                        parser=parser_kind,
                        status="unavailable",
                        reasonCode=exc.reason_code,
                        durationMs=_elapsed_ms(started),
                    )
                )
                continue
            except DocumentIngestionError as exc:
                attempts.append(
                    ParserAttempt(
                        parser=parser_kind,
                        status="failed",
                        reasonCode=exc.reason_code,
                        durationMs=_elapsed_ms(started),
                    )
                )
                continue
            except Exception:
                attempts.append(
                    ParserAttempt(
                        parser=parser_kind,
                        status="failed",
                        reasonCode=f"{parser_kind.upper()}_UNEXPECTED_FAILURE",
                        durationMs=_elapsed_ms(started),
                    )
                )
                continue

            attempts.append(
                ParserAttempt(parser=parser_kind, status="success", durationMs=_elapsed_ms(started))
            )
            metadata = {
                **result.metadata,
                "parserRoute": route.model_dump(mode="json"),
            }
            return result.model_copy(update={"attempts": attempts, "metadata": metadata})

        detail = ", ".join(f"{item.parser}:{item.reasonCode}" for item in attempts)
        raise DocumentParseError("DOCUMENT_PARSE_EXHAUSTED", detail)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
