from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.document_ingestion.adapters import (
    DocumentParserAdapter,
    ExternalWorkerDocumentAdapter,
    LightweightDocumentAdapter,
    PdfTextDocumentAdapter,
    SpreadsheetDocumentAdapter,
)
from app.document_ingestion.exceptions import DocumentParseError
from app.document_ingestion.models import DocumentNode, DocumentProbe, NormalizedDocument
from app.document_ingestion.router import DocumentParserRouter
from app.rag.document_contract import stable_hash
from scripts import document_parser_worker


class _StubAdapter(DocumentParserAdapter):
    def __init__(self, kind: str, *, fail: bool = False):
        self.kind = kind
        self.fail = fail

    def available(self) -> bool:
        return True

    def parse(self, path: Path, **kwargs: object) -> NormalizedDocument:
        if self.fail:
            raise DocumentParseError(f"{self.kind.upper()}_FIXTURE_FAILURE")
        probe = kwargs["probe"]
        assert isinstance(probe, DocumentProbe)
        return NormalizedDocument(
            documentId=str(kwargs["document_id"]),
            sourceName=str(kwargs["source_name"]),
            sourceType=str(kwargs["source_type"]),
            sourceUri=str(kwargs["source_uri"]),
            format=probe.format,
            mimeType=probe.mimeType,
            parser=self.kind,
            contentHash=stable_hash(path.read_bytes()),
            markdown="Recovered policy evidence.",
            nodes=[DocumentNode(nodeId="recovered-node-01", type="paragraph", order=0, text="Recovered")],
        )


def test_lightweight_html_preserves_business_structure(tmp_path: Path) -> None:
    path = tmp_path / "policy.html"
    path.write_text(
        """
        <html><body><h1>评价治理规范</h1><h2>有偿评价</h2>
        <p>不得通过返现诱导五星评价。</p><ol><li>保留交易证据</li></ol>
        <table><tr><th>风险</th><th>处置</th></tr><tr><td>刷单</td><td>人工复核</td></tr></table>
        </body></html>
        """,
        encoding="utf-8",
    )
    router = DocumentParserRouter(adapters=[LightweightDocumentAdapter()])

    result = router.parse(path, document_id="policy-html-001", source_type="regulation", language="zh")

    assert result.parser == "lightweight"
    assert result.attempts[0].status == "success"
    assert any(node.type == "title" and node.text == "评价治理规范" for node in result.nodes)
    assert any(node.type == "list_item" and "交易证据" in node.text for node in result.nodes)
    assert any(node.type == "table_row" and "刷单" in node.text for node in result.nodes)
    table = next(node for node in result.nodes if node.type == "table")
    assert len(table.children) == 2
    assert all(node.sectionPath for node in result.nodes if node.type not in {"title"})
    assert result.contentHash == stable_hash(path.read_bytes())


def test_lightweight_html_prefers_main_content_and_removes_site_controls(tmp_path: Path) -> None:
    path = tmp_path / "policy.html"
    path.write_text(
        """
        <html><body>
        <header role="banner"><h1>Government navigation</h1></header>
        <nav><p>Browse regulations</p></nav>
        <main><article><h1>Consumer Review Rule</h1><h2>Paid reviews</h2>
        <p>Businesses must not buy reviews conditioned on a positive sentiment.</p>
        <form><button>Was this page helpful?</button></form></article></main>
        <footer><p>Back to top</p></footer>
        </body></html>
        """,
        encoding="utf-8",
    )

    result = DocumentParserRouter(adapters=[LightweightDocumentAdapter()]).parse(
        path,
        document_id="policy-html-main-001",
        source_type="regulation",
        language="en",
    )

    assert "Consumer Review Rule" in result.markdown
    assert "conditioned on a positive sentiment" in result.markdown
    assert "Government navigation" not in result.markdown
    assert "Browse regulations" not in result.markdown
    assert "Was this page helpful" not in result.markdown
    assert "Back to top" not in result.markdown


def test_router_routes_document_types_by_structure_need() -> None:
    digital_pdf = DocumentProbe(format="pdf", mimeType="application/pdf", hasTextLayer=True)
    scanned_pdf = DocumentProbe(
        format="pdf",
        mimeType="application/pdf",
        hasTextLayer=False,
        requiresOcr=True,
        imageCoverageRatio=0.95,
    )
    spreadsheet = DocumentProbe(
        format="xlsx",
        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert DocumentParserRouter.select_route(digital_pdf).chain == ["pdf_text", "docling", "mineru"]
    scan_route = DocumentParserRouter.select_route(scanned_pdf)
    assert scan_route.chain == ["mineru", "docling"]
    assert scan_route.requiresGpuLease is True
    assert DocumentParserRouter.select_route(spreadsheet).chain == ["spreadsheet_native", "docling"]


def test_digital_pdf_fast_path_removes_repeated_layout_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def __init__(self, text: str):
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        def __init__(self, path: Path, strict: bool = False):
            self.pages = [
                FakePage("Agency Header\n1\nPART 465 - REVIEW RULE\n§ 465.2 Fake reviews are prohibited.\nAgency Footer"),
                FakePage("Agency Header\n2\n§ 465.4 Incentives must not condition review sentiment.\nAgency Footer"),
                FakePage("Agency Header\n3\n§ 465.7 Review suppression is prohibited.\nAgency Footer"),
            ]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=FakeReader, __version__="test-fast"))
    path = tmp_path / "digital.pdf"
    path.write_bytes(b"%PDF-fast-path-fixture")
    router = DocumentParserRouter(adapters=[PdfTextDocumentAdapter()])

    result = router.parse(
        path,
        document_id="digital-fast-001",
        source_name="Review Rule",
        source_type="regulation",
        language="en",
        probe=DocumentProbe(format="pdf", mimeType="application/pdf", hasTextLayer=True),
    )

    assert result.parser == "pdf_text"
    assert result.attempts[0].status == "success"
    assert "§ 465.4" in result.markdown
    assert "Agency Header" not in result.markdown
    assert "Agency Footer" not in result.markdown
    assert result.metadata["removedRepeatedLayoutLines"] >= 6


def test_pdf_probe_routes_missing_text_layer_to_ocr(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    path = tmp_path / "image-only-shape.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=600, height=800)
    with path.open("wb") as handle:
        writer.write(handle)

    probe = DocumentParserRouter(adapters=[]).probe(path)

    assert probe.hasTextLayer is False
    assert probe.requiresOcr is True
    assert DocumentParserRouter.select_route(probe).primary == "mineru"


def test_binary_document_never_falls_back_to_lightweight_text(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7\x00\xffbinary")
    router = DocumentParserRouter(adapters=[LightweightDocumentAdapter()])

    with pytest.raises(DocumentParseError) as caught:
        router.parse(
            path,
            document_id="broken-pdf-001",
            probe=DocumentProbe(format="pdf", mimeType="application/pdf", hasTextLayer=True),
        )

    assert caught.value.reason_code == "DOCUMENT_PARSE_EXHAUSTED"
    assert "docling:DOCLING_UNAVAILABLE" in str(caught.value)
    assert "mineru:MINERU_UNAVAILABLE" in str(caught.value)


def test_pdf_parser_failure_falls_back_to_next_structural_parser(tmp_path: Path) -> None:
    path = tmp_path / "policy.pdf"
    path.write_bytes(b"%PDF-fixture")
    router = DocumentParserRouter(
        adapters=[_StubAdapter("pdf_text", fail=True), _StubAdapter("docling", fail=True), _StubAdapter("mineru")]
    )

    result = router.parse(
        path,
        document_id="fallback-pdf-001",
        probe=DocumentProbe(format="pdf", mimeType="application/pdf", hasTextLayer=True),
    )

    assert result.parser == "mineru"
    assert [(item.parser, item.status) for item in result.attempts] == [
        ("pdf_text", "failed"),
        ("docling", "failed"),
        ("mineru", "success"),
    ]


def test_external_worker_contract_keeps_layout_and_assets(tmp_path: Path) -> None:
    worker = tmp_path / "fake_worker.py"
    worker.write_text(
        """
import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--parser'); p.add_argument('--input'); p.add_argument('--output'); p.add_argument('--bundle-dir')
a = p.parse_args()
bundle = Path(a.bundle_dir); bundle.mkdir(parents=True, exist_ok=True)
(bundle / 'figure.png').write_bytes(b'PNG-sample')
payload = {
  'parserVersion': 'test-1',
  'markdown': '# Policy\\n\\nPaid review evidence.',
  'elements': [
    {'type': 'title', 'text': 'Policy', 'sectionPath': ['Policy'], 'pageNumber': 1, 'sourceRef': '#/texts/0'},
    {'type': 'section', 'text': 'Paid reviews', 'sectionPath': ['Policy', 'Paid reviews'],
     'pageNumber': 1, 'sourceRef': '#/texts/1'},
    {'type': 'figure', 'text': 'Evidence flow', 'sectionPath': ['Policy'], 'pageNumber': 2,
     'bbox': {'left': 10, 'top': 20, 'right': 100, 'bottom': 80, 'coordinateSystem': 'top-left'},
     'assetRefs': ['figure-1'], 'sourceRef': '#/pictures/0'}
  ],
  'assets': [{'sourceRef': 'figure-1', 'kind': 'image', 'mediaType': 'image/png',
              'relativePath': 'figure.png', 'pageNumber': 2, 'caption': 'Evidence flow'}]
}
Path(a.output).write_text(json.dumps(payload), encoding='utf-8')
""",
        encoding="utf-8",
    )
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"%PDF-fake")
    artifact_root = tmp_path / "artifacts"
    adapter = ExternalWorkerDocumentAdapter(
        "docling",
        python_executable=sys.executable,
        worker_script=worker,
        artifact_root=artifact_root,
    )
    router = DocumentParserRouter(adapters=[adapter])

    result = router.parse(
        source,
        document_id="external-doc-001",
        probe=DocumentProbe(format="pdf", mimeType="application/pdf", hasTextLayer=True),
    )

    assert result.parser == "docling"
    assert result.parserVersion == "test-1"
    assert any(node.type == "section" and node.text == "Paid reviews" for node in result.nodes)
    figure = next(node for node in result.nodes if node.type == "figure")
    assert figure.pageNumber == 2
    assert figure.bbox is not None and figure.bbox.left == 10
    assert figure.assetIds == [result.assets[0].assetId]
    assert result.assets[0].relativePath == "external-doc-001/assets/figure.png"
    assert (artifact_root / result.assets[0].relativePath).is_file()


def test_docling_worker_uses_ascii_runtime_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = tmp_path / "environment_worker.py"
    worker.write_text(
        """
import argparse, json, os
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--parser'); p.add_argument('--input'); p.add_argument('--output'); p.add_argument('--bundle-dir')
a = p.parse_args()
keys = ['USERPROFILE', 'HOME', 'LOCALAPPDATA', 'APPDATA', 'TEMP', 'TMP', 'DOCLING_CACHE_DIR', 'HF_HOME']
payload = {
  'parserVersion': 'environment-test',
  'markdown': 'Controlled environment.',
  'elements': [{'type': 'paragraph', 'text': 'Controlled environment.', 'sourceRef': '#/texts/0'}],
  'assets': [],
  'metadata': {'workerEnvPaths': {key: os.getenv(key, '') for key in keys}}
}
Path(a.output).write_text(json.dumps(payload), encoding='utf-8')
""",
        encoding="utf-8",
    )
    source = tmp_path / "policy.pdf"
    source.write_bytes(b"%PDF-environment-fixture")
    runtime_root = Path(__file__).resolve().parents[1] / "artifacts" / "step242a" / "test-worker-runtime"
    monkeypatch.setenv("USERPROFILE", r"C:\Users\测试用户")
    monkeypatch.setenv("HOME", r"C:\Users\测试用户")
    monkeypatch.setenv("E_REVIEW_DOCUMENT_WORKER_ROOT", str(runtime_root))
    adapter = ExternalWorkerDocumentAdapter(
        "docling",
        python_executable=sys.executable,
        worker_script=worker,
    )
    router = DocumentParserRouter(adapters=[adapter])

    result = router.parse(
        source,
        document_id="worker-environment-001",
        probe=DocumentProbe(format="pdf", mimeType="application/pdf", hasTextLayer=True),
    )

    paths = result.metadata["workerEnvPaths"]
    assert all(value and str(value).isascii() for value in paths.values())
    assert Path(paths["TEMP"]).is_relative_to(runtime_root)


def test_xlsx_native_adapter_preserves_formula_and_merged_range(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "governance.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "审核规则"
    sheet.append(["风险", "数量", "加权值"])
    sheet.append(["有偿评价", 2, "=B2*10"])
    sheet.merge_cells("A4:C4")
    sheet["A4"] = "需要人工复核"
    workbook.save(path)
    workbook.close()
    router = DocumentParserRouter(adapters=[SpreadsheetDocumentAdapter()])

    result = router.parse(path, document_id="xlsx-policy-001", language="zh")

    assert result.parser == "spreadsheet_native"
    sheet_node = next(node for node in result.nodes if node.type == "sheet")
    assert "A4:C4" in sheet_node.metadata["mergedRanges"]
    formula_cells = [
        cell
        for node in result.nodes
        for cell in node.metadata.get("cells", [])
        if cell.get("isFormula")
    ]
    assert formula_cells == [{"coordinate": "C2", "value": "=B2*10", "dataType": "f", "isFormula": True}]
    assert "有偿评价" in result.markdown
    assert all(node.sourceRef for node in result.nodes)


def test_csv_table_root_is_traceable(tmp_path: Path) -> None:
    path = tmp_path / "governance.csv"
    path.write_text("风险,处置\n评分操纵,人工复核\n", encoding="utf-8")
    router = DocumentParserRouter(adapters=[LightweightDocumentAdapter()])

    result = router.parse(path, document_id="csv-policy-001", language="zh")

    assert all(node.sourceRef for node in result.nodes)


def test_normalized_document_rejects_broken_asset_reference() -> None:
    node = DocumentNode(
        nodeId="node-00000001",
        type="figure",
        order=0,
        assetIds=["asset-missing-01"],
    )
    with pytest.raises(ValidationError, match="DOCUMENT_ASSET_MISSING"):
        NormalizedDocument(
            documentId="broken-graph",
            sourceName="Broken",
            sourceType="test",
            format="pdf",
            mimeType="application/pdf",
            parser="docling",
            contentHash="content-hash-0001",
            nodes=[node],
        )


def test_bottom_left_bbox_accepts_docling_coordinate_order() -> None:
    from app.document_ingestion.models import BoundingBox

    bbox = BoundingBox(
        left=10,
        top=90,
        right=100,
        bottom=20,
        coordinateSystem="bottom-left",
    )
    assert bbox.top == 90


def test_mineru_content_is_sorted_by_page_and_visual_position() -> None:
    rows = [
        {"type": "text", "text": "第二段", "page_idx": 0, "bbox": [60, 120, 300, 150]},
        {"type": "header", "text": "文档标题", "page_idx": 0, "bbox": [60, 40, 300, 70]},
        {"type": "text", "text": "第一页", "page_idx": 0, "bbox": [60, 90, 300, 110]},
        {"type": "text", "text": "第二页", "page_idx": 1, "bbox": [60, 30, 300, 60]},
    ]

    ordered = document_parser_worker._order_mineru_content(rows)

    assert [item["text"] for item in ordered] == ["文档标题", "第一页", "第二段", "第二页"]


def test_parser_heading_normalization_promotes_only_first_visual_heading() -> None:
    assert document_parser_worker._promote_first_heading("section", order=0) == "title"
    assert document_parser_worker._promote_first_heading("section", order=1) == "section"
    assert document_parser_worker._mineru_type("header", is_document_start=True) == "title"
    assert document_parser_worker._mineru_type("header", is_document_start=False) == "paragraph"
