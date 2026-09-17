from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from app.document_ingestion.models import NormalizedDocument
from app.rag_quality.models import ParserFixtureExpectation


def evaluate_parsed_document(
    document: NormalizedDocument,
    expectation: ParserFixtureExpectation | dict[str, Any],
) -> dict[str, Any]:
    expected = (
        expectation
        if isinstance(expectation, ParserFixtureExpectation)
        else ParserFixtureExpectation.model_validate(expectation)
    )
    searchable = _normalize("\n".join([document.markdown, *(node.text for node in document.nodes)]))
    table_text = _normalize(
        "\n".join(
            [
                node.text
                + " "
                + " ".join(
                    _table_cell_text(cell)
                    for cell in node.metadata.get("cells", [])
                )
                for node in document.nodes
                if node.type in {"table", "table_row"}
            ]
        )
    )
    section_paths = {_normalize(" / ".join(node.sectionPath)) for node in document.nodes if node.sectionPath}
    node_types = Counter(node.type for node in document.nodes)
    anchor_hits = [_normalize(item) in searchable for item in expected.requiredAnchors]
    table_hits = [_normalize(item) in table_text for item in expected.requiredTableCells]
    section_hits = [
        any(_normalize(item) in path for path in section_paths)
        for item in expected.requiredSectionPaths
    ]
    node_type_hits = [node_types.get(item, 0) > 0 for item in expected.requiredNodeTypes]
    order_valid = _ordered(searchable, [_normalize(item) for item in expected.orderedAnchors])
    graph_traceability = all(
        node.nodeId and node.sourceRef and all(asset_id for asset_id in node.assetIds)
        for node in document.nodes
    )
    referenced_pages = {node.pageNumber for node in document.nodes if node.pageNumber is not None}
    route_reasons = set(document.metadata.get("parserRoute", {}).get("reasonCodes", []))
    asset_count_valid = len(document.assets) >= expected.minimumAssetCount
    asset_association_valid = (
        not expected.requireAssetAssociation
        or any(node.assetIds for node in document.nodes)
    )
    checks = {
        "formatMatches": document.format == expected.expectedFormat,
        "contentHashPresent": len(document.contentHash) >= 12,
        "markdownPresent": bool(document.markdown.strip()),
        "anchorsComplete": all(anchor_hits),
        "orderedAnchorsPreserved": order_valid,
        "requiredNodeTypesPresent": all(node_type_hits),
        "requiredSectionPathsPresent": all(section_hits),
        "requiredTableCellsPresent": all(table_hits),
        "requiredRouteReasonsPresent": set(expected.requiredRouteReasons).issubset(route_reasons),
        "nodeCountValid": len(document.nodes) >= expected.minimumNodeCount,
        "referencedPageCountValid": len(referenced_pages) >= expected.minimumReferencedPageCount,
        "graphTraceabilityComplete": graph_traceability,
        "assetCountValid": asset_count_valid,
        "assetAssociationValid": asset_association_valid,
    }
    return {
        "fixtureId": expected.fixtureId,
        "format": document.format,
        "parser": document.parser,
        "parserVersion": document.parserVersion,
        "checks": checks,
        "passed": all(checks.values()),
        "metrics": {
            "anchorRecall": _ratio(sum(anchor_hits), len(anchor_hits)),
            "nodeTypeRecall": _ratio(sum(node_type_hits), len(node_type_hits)),
            "sectionPathRecall": _ratio(sum(section_hits), len(section_hits)),
            "tableCellRecall": _ratio(sum(table_hits), len(table_hits)),
            "nodeCount": len(document.nodes),
            "referencedPageCount": len(referenced_pages),
            "assetCount": len(document.assets),
        },
        "nodeTypes": dict(sorted(node_types.items())),
        "warnings": document.warnings,
        "attempts": [item.model_dump(mode="json") for item in document.attempts],
    }


def aggregate_parser_results(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(results)
    failed = [row for row in rows if not row.get("passed")]
    return {
        "schemaVersion": "rag-quality-parser-result-v1",
        "fixtureCount": len(rows),
        "passedFixtureCount": len(rows) - len(failed),
        "parseSuccessRate": _ratio(len(rows) - len(failed), len(rows)),
        "silentParserLossCount": len(failed),
        "hardSafetyGate": "PASS" if rows and not failed else "FAIL",
        "failures": failed,
        "results": rows,
    }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _table_cell_text(cell: Any) -> str:
    if isinstance(cell, dict):
        return str(cell.get("value", cell.get("text", "")))
    return str(cell)


def _ordered(content: str, anchors: list[str]) -> bool:
    if not anchors:
        return True
    offset = 0
    for anchor in anchors:
        index = content.find(anchor, offset)
        if index < 0:
            return False
        offset = index + len(anchor)
    return True


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0
