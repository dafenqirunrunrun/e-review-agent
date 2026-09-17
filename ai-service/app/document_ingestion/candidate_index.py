"""Build and publish versioned policy indexes from parsed document-library files."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings
from app.document_ingestion.models import NormalizedDocument
from app.document_ingestion.release_evaluation import evaluate_policy_release
from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.embedding import PolicyEmbeddingProvider, create_policy_embedding_provider
from app.policy_rag.index_store import load_policy_chunks, write_policy_chunks
from app.policy_rag.models import ParsedPolicyDocument, PolicyChunk, PolicySourceManifest, utc_now
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.vector_store import DEFAULT_FAISS_META_NAME, DEFAULT_FAISS_NAME, build_policy_faiss_index
from app.rag.document_contract import stable_hash
from app.rag.chunking import count_tokens


VERSION_RE = re.compile(r"policy-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}")
MANIFEST_NAME = "release_manifest.json"
MANIFEST_CHECKSUM_NAME = "release_manifest.sha256"
CHUNKS_NAME = "policy_chunks.jsonl"
SMOKE_QUERIES = (
    ("刷单 好评返现 五星截图", "rating_manipulation"),
    ("删除差评 压制负面评价", "review_suppression"),
    ("退款 退货 售后", "after_sales_risk"),
)


def build_candidate(
    request_path: Path | str,
    *,
    embedding_provider: PolicyEmbeddingProvider | None = None,
) -> dict[str, Any]:
    request_file = Path(request_path).resolve()
    request = json.loads(request_file.read_text(encoding="utf-8-sig"))
    document_root = Path(request["documentRoot"]).resolve()
    index_root = Path(request["indexRoot"]).resolve()
    version = _version(request["version"])
    release_id = str(request["releaseId"])
    staging = index_root / "versions" / f"{version}.staging"
    _assert_child(staging, index_root)
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)

    base_index_path = PolicyEvidenceRetriever._resolve_index_path(
        str(request.get("baseIndexPath", settings.policy_rag.index_path))
    )
    active_version, active_directory = _active_index(index_root)
    if active_directory is not None:
        inherited_chunks = load_policy_chunks(active_directory / CHUNKS_NAME)
        # Every request materializes the complete desired uploaded-document set.
        # Remove the previous uploaded layer, then add the current documents.
        base_chunks = [
            chunk for chunk in inherited_chunks
            if str(chunk.metadata.get("sourceOrigin") or "") != "document_library"
        ]
        reuse_directory: Path | None = active_directory
        reference_directory: Path | None = active_directory
    else:
        base_chunks = load_policy_chunks(base_index_path) if base_index_path.is_file() else []
        reuse_directory = base_index_path.parent if base_index_path.is_file() else None
        reference_directory = reuse_directory
    uploaded_chunks: list[PolicyChunk] = []
    source_manifests: list[dict[str, Any]] = []
    purification = {
        "rawChunkCount": 0,
        "indexedChunkCount": 0,
        "droppedNoiseCount": 0,
        "droppedTinyCount": 0,
        "mergedChunkCount": 0,
        "deduplicatedCount": 0,
    }
    for item in request.get("documents") or []:
        normalized_path = (document_root / str(item["resultPath"])).resolve()
        _assert_child(normalized_path, document_root)
        document = NormalizedDocument.model_validate_json(normalized_path.read_text(encoding="utf-8-sig"))
        if document.documentId != item["documentId"]:
            raise ValueError("INDEX_DOCUMENT_ID_MISMATCH")
        if str(document.metadata.get("fileHash") or "") != str(item.get("fileHash") or ""):
            raise ValueError("INDEX_DOCUMENT_HASH_MISMATCH")
        parsed = _as_policy_document(document, item)
        source_manifest = parsed.manifest.model_dump(mode="json")
        # Uploaded policies often contain short but decisive rules such as
        # "禁止删除差评". Keep them without changing the frozen corpus chunker.
        raw_chunks = PolicyStructureChunker(min_chars=6, min_tokens=2).chunk(parsed)
        clean_chunks, stats = _purify_source_chunks(raw_chunks)
        source_manifest["metadata"]["indexPurification"] = stats
        source_manifests.append(source_manifest)
        uploaded_chunks.extend(clean_chunks)
        for name in purification:
            purification[name] += stats.get(name, 0)

    allow_empty_uploads = bool(request.get("allowEmptyUploads", False))
    if not uploaded_chunks and not allow_empty_uploads:
        raise ValueError("INDEX_NO_POLICY_CHUNKS")
    combined = [*base_chunks, *uploaded_chunks]
    chunks = _dedupe(combined)
    purification["deduplicatedCount"] = len(combined) - len(chunks)
    purification["indexedChunkCount"] = len(uploaded_chunks)
    chunks_path = staging / CHUNKS_NAME
    write_policy_chunks(chunks_path, chunks)

    dense_required = bool(request.get("denseRequired", True))
    provider = embedding_provider or create_policy_embedding_provider()
    dense = build_policy_faiss_index(
        chunks,
        output_dir=staging,
        provider=provider,
        reuse_dir=reuse_directory,
    )
    release_evaluation = evaluate_policy_release(
        staging,
        reference_dir=reference_directory,
        provider=provider,
    )
    if dense.get("status") != "ready":
        release_evaluation["decision"] = "blocked"
        release_evaluation["decisionLabel"] = "禁止发布"
        release_evaluation["gatePassed"] = False
        release_evaluation["reasonCodes"] = list(dict.fromkeys([
            *(release_evaluation.get("reasonCodes") or []),
            "DENSE_INDEX_UNAVAILABLE",
        ]))
    citation_failures = _citation_failures(chunks)
    smoke = _smoke_results(chunks)
    checks = {
        "hasUploadedChunks": bool(uploaded_chunks) or (allow_empty_uploads and bool(chunks)),
        "allCitationsTraceable": not citation_failures,
        "bm25SmokePassed": all(item["passed"] for item in smoke),
        "denseReady": dense.get("status") == "ready" if dense_required else True,
        "denseCountMatches": dense.get("vectorCount") == len(chunks) if dense.get("status") == "ready" else not dense_required,
        "releaseEvaluationPassed": bool(release_evaluation.get("gatePassed")),
    }
    gate = "PASS" if all(checks.values()) else "FAIL"
    manifest = {
        "schemaVersion": "document-policy-index-release-v1",
        "releaseId": release_id,
        "version": version,
        "status": "ready" if gate == "PASS" else "failed",
        "gate": gate,
        "builtAt": utc_now(),
        "baseChunkCount": len(base_chunks),
        "uploadedDocumentCount": len(source_manifests),
        "uploadedChunkCount": len(uploaded_chunks),
        "chunkCount": len(chunks),
        "purification": purification,
        "indexHash": stable_hash("|".join(chunk.contentHash for chunk in chunks)),
        "checks": checks,
        "citationFailures": citation_failures[:20],
        "smoke": smoke,
        "dense": _redact_dense(dense),
        "incremental": {
            "previousActiveVersion": active_version or "",
            "baseChunkCount": len(base_chunks),
            **(dense.get("incremental") or {
                "status": "not_available",
                "reusedVectorCount": 0,
                "embeddedVectorCount": len(chunks),
                "removedVectorCount": 0,
                "sourceVectorCount": 0,
            }),
        },
        "releaseEvaluation": release_evaluation,
        "sources": source_manifests,
    }
    manifest_path = staging / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    manifest["artifactChecksums"] = _artifact_checksums(staging, dense.get("status") == "ready")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (staging / MANIFEST_CHECKSUM_NAME).write_text(_sha256(manifest_path) + "\n", encoding="ascii", newline="\n")
    return manifest


class PolicyIndexReleaseStore:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.versions = self.root / "versions"
        self.active_pointer = self.root / "ACTIVE"
        self.versions.mkdir(parents=True, exist_ok=True)

    def publish(self, version: str) -> dict[str, Any]:
        version = _version(version)
        staging = self.versions / f"{version}.staging"
        final = self.versions / version
        source = staging if staging.is_dir() else final
        if not source.is_dir():
            raise ValueError("INDEX_STAGING_VERSION_NOT_FOUND")
        manifest = self._validate(source)
        if manifest.get("gate") != "PASS":
            raise ValueError("INDEX_QUALITY_GATE_NOT_PASSED")
        previous = self.active_version()
        if source == staging:
            if final.exists():
                raise ValueError("INDEX_VERSION_ALREADY_PUBLISHED")
            staging.replace(final)
        self._write_pointer(version)
        return {**manifest, "active": True, "previousVersion": previous or ""}

    def rollback(self, version: str) -> dict[str, Any]:
        version = _version(version)
        target = self.versions / version
        if not target.is_dir():
            raise ValueError("INDEX_ROLLBACK_VERSION_NOT_FOUND")
        manifest = self._validate(target)
        previous = self.active_version()
        self._write_pointer(version)
        return {**manifest, "active": True, "previousVersion": previous or ""}

    def deactivate(self, expected_version: str) -> dict[str, Any]:
        expected_version = _version(expected_version)
        if self.active_version() != expected_version:
            raise ValueError("INDEX_DEACTIVATE_VERSION_MISMATCH")
        self.active_pointer.unlink()
        return {"version": expected_version, "active": False}

    def active_version(self) -> str | None:
        if not self.active_pointer.is_file():
            return None
        value = self.active_pointer.read_text(encoding="utf-8-sig").strip()
        return _version(value) if value else None

    def _write_pointer(self, version: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(version + "\n")
            stream.flush()
        temporary.replace(self.active_pointer)

    @staticmethod
    def _validate(directory: Path) -> dict[str, Any]:
        manifest_path = directory / MANIFEST_NAME
        checksum_path = directory / MANIFEST_CHECKSUM_NAME
        if not checksum_path.is_file() or checksum_path.read_text(encoding="ascii").strip() != _sha256(manifest_path):
            raise ValueError("INDEX_MANIFEST_CHECKSUM_MISMATCH")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        expected = manifest.get("artifactChecksums") or {}
        if not expected:
            raise ValueError("INDEX_CHECKSUMS_MISSING")
        for name, checksum in expected.items():
            path = directory / name
            if not path.is_file() or _sha256(path) != checksum:
                raise ValueError("INDEX_ARTIFACT_CHECKSUM_MISMATCH")
        return manifest


def _as_policy_document(document: NormalizedDocument, item: dict[str, Any]) -> ParsedPolicyDocument:
    source_name = str(item.get("sourceName") or document.sourceName)
    source_url = str(item.get("sourceUrl") or document.sourceUri or f"document:{document.documentId}")
    markdown, scope = _index_markdown(document, source_name, source_url)
    if not markdown:
        markdown = "\n\n".join(node.text.strip() for node in document.nodes if node.text.strip())
    profile = _source_profile(source_url, source_name, markdown, document.language)
    manifest = PolicySourceManifest.from_content(
        content=markdown,
        sourceId=document.documentId,
        sourceUrl=source_url,
        sourceName=source_name,
        sourceType=profile["sourceType"],
        jurisdiction=profile["jurisdiction"],
        language=profile["language"],
        parser=_policy_parser(document.parser, document.format),
        parserVersion=document.parserVersion,
        licenseClass=profile["licenseClass"],
        metadata={
            "uploadedDocumentId": document.documentId,
            "sourceOrigin": "document_library",
            "normalizedContentHash": document.contentHash,
            "originalParser": document.parser,
            "fileHash": str(item.get("fileHash") or document.metadata.get("fileHash") or ""),
            "indexScope": scope,
        },
    )
    return ParsedPolicyDocument(manifest=manifest, markdown=markdown, structured={"format": document.format})


def _policy_parser(parser: str, document_format: str) -> str:
    if parser == "lightweight":
        return {"html": "lightweight_html", "text": "plain_text", "csv": "plain_text"}.get(document_format, "manual_markdown")
    return {
        "mineru": "mineru",
        "docling": "docling",
        "pdf_text": "pypdf_text",
        "spreadsheet_native": "spreadsheet_native",
    }.get(parser, "manual_markdown")


def _index_markdown(document: NormalizedDocument, source_name: str, source_url: str) -> tuple[str, str]:
    markdown = document.markdown.strip()
    identity = f"{source_name} {source_url}".lower()
    if document.format == "pdf" and "ftc" in identity and "final" in identity:
        matches = list(re.finditer(r"(?im)^#{0,3}\s*PART\s+465(?:\s*[—-].*)?$", markdown))
        for match in reversed(matches):
            candidate = markdown[match.start():].strip()
            if re.search(r"§\s*465\.1", candidate):
                return f"# {source_name}\n\n{candidate}", "formal_rule"
    return markdown, "full_document"


def _source_profile(source_url: str, source_name: str, text: str, language: str) -> dict[str, str]:
    host = urlparse(source_url).hostname or ""
    identity = f"{host} {source_name}".lower()
    inferred_language = language if language and language != "und" else _infer_language(text)
    if "ecfr.gov" in host or "ftc.gov" in host:
        return {"sourceType": "regulation", "jurisdiction": "US", "language": inferred_language, "licenseClass": "public_domain"}
    if any(value in host for value in ("mofcom.gov.cn", "samr.gov.cn", "moj.gov.cn")):
        return {"sourceType": "law", "jurisdiction": "CN", "language": "zh", "licenseClass": "public_reference_restricted"}
    if "gov.uk" in host or "competition and markets authority" in identity:
        return {"sourceType": "regulation", "jurisdiction": "UK", "language": inferred_language, "licenseClass": "public_reference_restricted"}
    if ".gc.ca" in host or "canada" in identity:
        return {"sourceType": "regulation", "jurisdiction": "CA", "language": inferred_language, "licenseClass": "public_reference_restricted"}
    if "support.google.com" in host or "amazon." in host:
        return {"sourceType": "platform_policy", "jurisdiction": "GLOBAL", "language": inferred_language, "licenseClass": "public_reference_restricted"}
    return {"sourceType": "policy", "jurisdiction": "uploaded", "language": inferred_language, "licenseClass": "project_owned"}


def _infer_language(text: str) -> str:
    sample = text[:20000]
    cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    return "zh" if cjk > max(20, latin * 0.25) else "en"


NOISE_PATTERNS = (
    "back to top",
    "skip to main content",
    "print this page",
    "share this page",
    "we use some essential cookies",
    "accept additional cookies",
    "reject additional cookies",
    "unsupported browser",
    "site feedback",
    "sign in to your account",
)


def _purify_source_chunks(chunks: list[PolicyChunk]) -> tuple[list[PolicyChunk], dict[str, int]]:
    filtered: list[PolicyChunk] = []
    stats = {
        "rawChunkCount": len(chunks),
        "indexedChunkCount": 0,
        "droppedNoiseCount": 0,
        "droppedTinyCount": 0,
        "mergedChunkCount": 0,
        "deduplicatedCount": 0,
    }
    seen: set[str] = set()
    for chunk in chunks:
        normalized = _normalized_chunk_text(chunk.text)
        if _is_noise_chunk(normalized):
            stats["droppedNoiseCount"] += 1
            continue
        block_type = str(chunk.metadata.get("blockType") or "")
        business_bearing = chunk.riskTypes != ["review_policy"] or block_type in {"clause", "table"}
        if chunk.tokenCount < 8 and not business_bearing:
            stats["droppedTinyCount"] += 1
            continue
        fingerprint = stable_hash(normalized)
        if fingerprint in seen:
            stats["deduplicatedCount"] += 1
            continue
        seen.add(fingerprint)
        tier = "A" if business_bearing else "B"
        filtered.append(chunk.model_copy(update={"metadata": {**chunk.metadata, "contentTier": tier}}))

    compacted: list[PolicyChunk] = []
    for chunk in filtered:
        if compacted and _can_merge(compacted[-1], chunk):
            compacted[-1] = _merge_chunks(compacted[-1], chunk)
            stats["mergedChunkCount"] += 1
        else:
            compacted.append(chunk)
    stats["indexedChunkCount"] = len(compacted)
    return compacted, stats


def _normalized_chunk_text(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text.lower()).strip()


def _is_noise_chunk(normalized: str) -> bool:
    if not normalized:
        return True
    return any(pattern in normalized for pattern in NOISE_PATTERNS)


def _can_merge(left: PolicyChunk, right: PolicyChunk) -> bool:
    if left.documentId != right.documentId or left.sectionPath != right.sectionPath or left.clauseId != right.clauseId:
        return False
    if left.metadata.get("blockType") != "paragraph" or right.metadata.get("blockType") != "paragraph":
        return False
    return left.tokenCount < 60 and count_tokens(f"{left.text}\n\n{right.text}") <= 120


def _merge_chunks(left: PolicyChunk, right: PolicyChunk) -> PolicyChunk:
    text = f"{left.text.rstrip()}\n\n{right.text.lstrip()}"
    content_hash = stable_hash(text)
    metadata = {**left.metadata, "mergedBlocks": int(left.metadata.get("mergedBlocks", 1)) + int(right.metadata.get("mergedBlocks", 1))}
    return left.model_copy(update={
        "chunkId": stable_hash(f"{left.documentId}:merged:{content_hash}")[:24],
        "text": text,
        "contentHash": content_hash,
        "tokenCount": count_tokens(text),
        "riskTypes": list(dict.fromkeys([*left.riskTypes, *right.riskTypes])),
        "evidenceTags": list(dict.fromkeys([*left.evidenceTags, *right.evidenceTags])),
        "parentChunkId": stable_hash(f"{left.documentId}:parent:{left.sectionPath}:{content_hash}")[:24],
        "metadata": metadata,
    })


def _base_chunks(value: str) -> list[PolicyChunk]:
    path = PolicyEvidenceRetriever._resolve_index_path(str(value))
    return load_policy_chunks(path) if path.is_file() else []


def _active_index(index_root: Path) -> tuple[str | None, Path | None]:
    pointer = index_root / "ACTIVE"
    if not pointer.is_file():
        return None, None
    version = _version(pointer.read_text(encoding="utf-8-sig").strip())
    directory = index_root / "versions" / version
    _assert_child(directory, index_root)
    if not directory.is_dir() or not (directory / CHUNKS_NAME).is_file():
        raise ValueError("ACTIVE_INDEX_ARTIFACT_MISSING")
    return version, directory


def _dedupe(chunks: list[PolicyChunk]) -> list[PolicyChunk]:
    output: list[PolicyChunk] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        source_scope = chunk.sourceUrl.rstrip("/").lower() or chunk.documentId
        key = (source_scope, stable_hash(_normalized_chunk_text(chunk.text)))
        if key not in seen:
            output.append(chunk)
            seen.add(key)
    return output


def _citation_failures(chunks: list[PolicyChunk]) -> list[dict[str, str]]:
    failures = []
    for chunk in chunks:
        missing = [name for name, value in (
            ("sourceName", chunk.sourceName), ("sourceUrl", chunk.sourceUrl),
            ("sectionPath", chunk.sectionPath), ("contentHash", chunk.contentHash),
        ) if not value]
        if missing:
            failures.append({"chunkId": chunk.chunkId, "missing": ",".join(missing)})
    return failures


def _smoke_results(chunks: list[PolicyChunk]) -> list[dict[str, Any]]:
    retriever = PolicyEvidenceRetriever(chunks)
    output = []
    for query, risk in SMOKE_QUERIES:
        hits = retriever.search(query, risk_hints=[risk], top_k=3, mode="bm25")
        output.append({"query": query, "riskType": risk, "passed": bool(hits), "topChunkIds": [hit.chunkId for hit in hits]})
    return output


def _artifact_checksums(directory: Path, dense_ready: bool) -> dict[str, str]:
    names = [CHUNKS_NAME]
    if dense_ready:
        names.extend([DEFAULT_FAISS_NAME, DEFAULT_FAISS_META_NAME])
    return {name: _sha256(directory / name) for name in names}


def _redact_dense(dense: dict[str, Any]) -> dict[str, Any]:
    output = {key: value for key, value in dense.items() if key not in {"indexPath", "metaPath"}}
    provider = output.get("provider")
    if isinstance(provider, dict):
        provider = dict(provider)
        provider["modelPath"] = "configured" if provider.get("modelPath") else "not_configured"
        output["provider"] = provider
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_child(path: Path, root: Path) -> None:
    if not path.is_relative_to(root):
        raise ValueError("INDEX_PATH_OUTSIDE_ROOT")


def _version(value: str) -> str:
    version = str(value or "")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("INDEX_VERSION_INVALID")
    return version
