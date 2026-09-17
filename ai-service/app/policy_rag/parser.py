from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.policy_rag.models import ParsedPolicyDocument, PolicySourceManifest


COMPLEX_SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx"}
HTML_SUFFIXES = {".html", ".htm"}
XML_SUFFIXES = {".xml"}
CJK_INTERCHARACTER_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff])[ \t\f\v]+(?=[\u4e00-\u9fff])")


class PolicyDocumentParser:
    """Unified parser for public policy sources.

    MinerU is optional and treated as an external pre-processing dependency. If
    it is not available, parsing falls back to lightweight text/Markdown
    normalization so local demos and tests stay dependency-free.
    """

    def __init__(self, *, mineru_command: str | None = None):
        self.mineru_command = mineru_command or os.getenv("MINERU_CLI", "mineru")

    def parse_text(
        self,
        *,
        source_id: str,
        source_url: str,
        source_name: str,
        source_type: str,
        content: str,
        language: str = "en",
        jurisdiction: str = "platform",
        license_class: str = "public_reference_restricted",
        parser: str = "manual_markdown",
        metadata: dict[str, Any] | None = None,
    ) -> ParsedPolicyDocument:
        normalized = self._normalize_markdown(content)
        manifest = PolicySourceManifest.from_content(
            sourceId=source_id,
            sourceUrl=source_url,
            sourceName=source_name,
            sourceType=source_type,
            jurisdiction=jurisdiction,
            language=language,
            parser=parser,  # type: ignore[arg-type]
            licenseClass=license_class,  # type: ignore[arg-type]
            content=normalized,
            metadata=metadata or {},
        )
        return ParsedPolicyDocument(manifest=manifest, markdown=normalized, structured={"format": "markdown"})

    def parse_file(
        self,
        path: Path,
        *,
        source_id: str,
        source_url: str,
        source_name: str,
        source_type: str,
        language: str = "en",
        jurisdiction: str = "platform",
        license_class: str = "public_reference_restricted",
    ) -> ParsedPolicyDocument:
        suffix = path.suffix.lower()
        if suffix in COMPLEX_SUFFIXES:
            parsed = self._try_mineru(path)
            if parsed is not None:
                return self.parse_text(
                    source_id=source_id,
                    source_url=source_url,
                    source_name=source_name,
                    source_type=source_type,
                    content=parsed,
                    language=language,
                    jurisdiction=jurisdiction,
                    license_class=license_class,
                    parser="mineru",
                    metadata={"source_file": path.name},
                )
            if suffix == ".pdf":
                extracted = self._extract_pdf_text(path)
                if extracted:
                    return self.parse_text(
                        source_id=source_id,
                        source_url=source_url,
                        source_name=source_name,
                        source_type=source_type,
                        content=extracted,
                        language=language,
                        jurisdiction=jurisdiction,
                        license_class=license_class,
                        parser="plain_text",
                        metadata={"source_file": path.name, "mineru_fallback": True, "pdf_extraction": "pypdf"},
                    )
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        if suffix in HTML_SUFFIXES:
            content = self._html_to_markdown(content)
            parser = "lightweight_html"
        elif suffix in XML_SUFFIXES:
            content = self._xml_to_markdown(content)
            parser = "lightweight_html"
        else:
            parser = "manual_markdown" if suffix in {".md", ".markdown"} else "plain_text"
        return self.parse_text(
            source_id=source_id,
            source_url=source_url,
            source_name=source_name,
            source_type=source_type,
            content=content,
            language=language,
            jurisdiction=jurisdiction,
            license_class=license_class,
            parser=parser,
            metadata={"source_file": path.name, "mineru_fallback": suffix in COMPLEX_SUFFIXES},
        )

    @staticmethod
    def _extract_pdf_text(path: Path) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception:
            return ""
        return "\n\n".join(page.strip() for page in pages if page.strip())

    def _try_mineru(self, path: Path) -> str | None:
        command = shutil.which(self.mineru_command)
        if not command:
            return None
        output_dir = Path(os.getenv("MINERU_OUTPUT_DIR", "")).expanduser() if os.getenv("MINERU_OUTPUT_DIR") else None
        before = set(output_dir.rglob("*.md")) if output_dir and output_dir.exists() else set()
        try:
            completed = subprocess.run(
                [command, str(path)],
                capture_output=True,
                text=True,
                timeout=int(os.getenv("MINERU_TIMEOUT_SECONDS", "120")),
                check=False,
            )
        except Exception:
            return None
        if completed.returncode != 0:
            return None
        output = completed.stdout.strip()
        if output:
            return output
        if output_dir and output_dir.exists():
            candidates = [item for item in output_dir.rglob("*.md") if item not in before]
            if candidates:
                newest = max(candidates, key=lambda item: item.stat().st_mtime)
                return newest.read_text(encoding="utf-8-sig", errors="replace")
        return None

    @staticmethod
    def _normalize_markdown(content: str) -> str:
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        # Some PDF text layers emit Chinese glyphs as `格 式 条 款`.  Keeping
        # those horizontal gaps makes BM25 tokenization and embedding retrieval
        # treat a legal clause as mostly single characters.  Newlines stay
        # intact so headings, lists, tables, and page boundaries are preserved.
        text = CJK_INTERCHARACTER_SPACE_RE.sub("", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _html_to_markdown(content: str) -> str:
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
        text = re.sub(r"<(?:nav|footer|header|aside)\b[^>]*>.*?</(?:nav|footer|header|aside)>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        for level in range(1, 7):
            text = re.sub(
                rf"<h{level}[^>]*>(.*?)</h{level}>",
                lambda match, level=level: "\n" + "#" * level + " " + _strip_tags(match.group(1)).strip() + "\n",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<tr[^>]*>(.*?)</tr>", lambda match: "\n| " + " | ".join(_table_cells(match.group(1))) + " |\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<li[^>]*>(.*?)</li>", lambda match: "\n- " + _strip_tags(match.group(1)).strip(), text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"</(?:p|div|section|article|tr)>", "\n", text, flags=re.IGNORECASE)
        text = _strip_tags_preserve_lines(text)
        return html.unescape(text)

    @staticmethod
    def _xml_to_markdown(content: str) -> str:
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"<HEAD[^>]*>(.*?)</HEAD>", lambda match: "\n## " + _strip_tags(match.group(1)).strip() + "\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<SECTNO[^>]*>(.*?)</SECTNO>", lambda match: "\n### " + _strip_tags(match.group(1)).strip() + "\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<SUBJECT[^>]*>(.*?)</SUBJECT>", lambda match: " " + _strip_tags(match.group(1)).strip() + "\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<P[^>]*>(.*?)</P>", lambda match: "\n" + _strip_tags(match.group(1)).strip() + "\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = _strip_tags_preserve_lines(text)
        text = html.unescape(text)
        text = re.sub(r"§\s+([0-9])", r"§ \1", text)
        return text


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags_preserve_lines(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _table_cells(value: str) -> list[str]:
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", value, flags=re.IGNORECASE | re.DOTALL)
    return [_strip_tags(cell) for cell in cells if _strip_tags(cell)] or [_strip_tags(value)]
