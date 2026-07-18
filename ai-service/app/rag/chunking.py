from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.document_contract import ChunkRecord, DocumentRecord, stable_hash


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")


def count_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


@dataclass(frozen=True)
class HierarchicalChunk:
    content: str
    record: ChunkRecord
    parent_content: str | None = None


class HierarchicalChunker:
    def __init__(self, parent_tokens: int = 700, child_tokens: int = 220, overlap_tokens: int = 48):
        if child_tokens <= overlap_tokens:
            raise ValueError("child_tokens must exceed overlap_tokens")
        self.parent_tokens = parent_tokens
        self.child_tokens = child_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, document: DocumentRecord, content: str) -> list[HierarchicalChunk]:
        sections = self._heading_sections(content)
        parents: list[tuple[str, list[str]]] = []
        for heading, text in sections:
            tokens = TOKEN_RE.findall(text)
            for window in self._windows(tokens, self.parent_tokens, 0):
                parents.append((heading, window))
        output: list[HierarchicalChunk] = []
        index = 0
        for heading, parent_tokens in parents:
            parent_text = "".join(parent_tokens)
            parent_id = stable_hash(f"{document.document_id}:{document.document_version}:parent:{index}:{parent_text}")[:24]
            for child_tokens in self._windows(parent_tokens, self.child_tokens, self.overlap_tokens):
                child_text = "".join(child_tokens)
                record = ChunkRecord.from_content(
                    document_id=document.document_id,
                    document_version=document.document_version,
                    chunk_index=index,
                    content=child_text,
                    token_count=len(child_tokens),
                    parent_chunk_id=parent_id,
                    trust_level=document.trust_level,
                    metadata={**document.metadata, "heading": heading, "tenant_id": document.tenant_id},
                )
                output.append(HierarchicalChunk(content=child_text, record=record, parent_content=parent_text))
                index += 1
        return output

    @staticmethod
    def _heading_sections(content: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_heading = "root"
        current_lines: list[str] = []
        for line in content.splitlines():
            if line.strip().startswith("#"):
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines)))
                    current_lines = []
                current_heading = line.strip("# ").strip() or "root"
            else:
                current_lines.append(line)
        if current_lines:
            sections.append((current_heading, "\n".join(current_lines)))
        return sections or [("root", content)]

    @staticmethod
    def _windows(tokens: list[str], size: int, overlap: int) -> list[list[str]]:
        if not tokens:
            return [[]]
        step = max(1, size - overlap)
        return [tokens[i : i + size] for i in range(0, len(tokens), step)]
