from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.policy_rag.models import ParsedPolicyDocument, PolicyChunk
from app.rag.chunking import TOKEN_RE as COUNT_TOKEN_RE, count_tokens
from app.rag.document_contract import stable_hash


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CLAUSE_RE = re.compile(
    r"^(?:§\s*([0-9]+(?:\.[0-9A-Za-z-]+)*)|"
    r"Article\s+([0-9A-Za-z.-]+)|"
    # Chinese clause text may continue immediately after `条`; a Western word
    # boundary rejects `第二十四条经营者...` after PDF-space normalization.
    r"第\s*([一二三四五六七八九十百千万0-9]+)\s*条)",
    re.IGNORECASE,
)
LIST_RE = re.compile(r"^\s*(?:[-*+]|\(?[0-9A-Za-z]+\)|[0-9A-Za-z]+[.)]|[一二三四五六七八九十]+[、.])\s+")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
PAGE_MARKER_RE = re.compile(r"^(?:[—–-]\s*)?\d+\s*(?:[—–-])?$")

RISK_KEYWORDS = {
    "fake_review": ["fake", "false", "misleading", "fabricated", "虚假", "刷单", "编造"],
    "rating_manipulation": ["rating", "incentive", "paid", "cashback", "compensation", "好评返现", "五星截图", "评分", "操纵"],
    "review_suppression": ["suppress", "remove", "delete", "threaten", "unfavorable review", "删除", "屏蔽", "压制", "差评"],
    "privacy_risk": ["privacy", "personal information", "隐私", "个人信息"],
    "harassment_or_abuse": ["harass", "threat", "abuse", "威胁", "辱骂", "骚扰"],
    "after_sales_risk": [
        "refund",
        "return",
        "after-sales",
        "退款",
        "退货",
        "售后",
        "破损",
        "质量",
        "换货",
        "修理",
        "返还",
        "退还",
        "价款",
        "运费",
    ],
    "safety_or_fraud_risk": ["unsafe", "safety", "fraud", "danger", "安全", "欺诈", "假货", "危险"],
}


@dataclass
class _Block:
    text: str
    heading: str
    section_path: list[str] = field(default_factory=list)
    clause_id: str = ""
    block_type: str = "paragraph"


class PolicyStructureChunker:
    def __init__(
        self,
        *,
        child_max_tokens: int = 220,
        child_overlap_tokens: int = 32,
        min_chars: int = 12,
        min_tokens: int = 4,
    ):
        if child_max_tokens <= child_overlap_tokens:
            raise ValueError("child_max_tokens must exceed child_overlap_tokens")
        self.child_max_tokens = child_max_tokens
        self.child_overlap_tokens = child_overlap_tokens
        self.min_chars = min_chars
        self.min_tokens = min_tokens

    def chunk(self, document: ParsedPolicyDocument) -> list[PolicyChunk]:
        blocks = self._blocks(document.markdown)
        chunks: list[PolicyChunk] = []
        seen_chunks: set[tuple[tuple[str, ...], str]] = set()
        index = 0
        for block in blocks:
            if len(block.text.strip()) < self.min_chars:
                continue
            parent_id = stable_hash(f"{document.manifest.sourceId}:parent:{block.heading}:{block.clause_id}:{block.text}")[:24]
            clause_context = self._clause_context(block.clause_id)
            for child_text in self._children(block.text, clause_context=clause_context):
                token_count = count_tokens(child_text)
                if len(child_text.strip()) < self.min_chars or token_count < self.min_tokens:
                    continue
                content_hash = stable_hash(child_text)
                dedupe_key = (tuple(block.section_path), content_hash)
                if dedupe_key in seen_chunks:
                    continue
                seen_chunks.add(dedupe_key)
                risk_types = self._risk_types(child_text, block.heading)
                evidence_tags = self._evidence_tags(child_text, risk_types)
                heading = block.heading if block.heading and block.heading != "root" else clause_context or document.manifest.sourceName
                chunks.append(
                    PolicyChunk(
                        chunkId=stable_hash(f"{document.manifest.sourceId}:{index}:{content_hash}")[:24],
                        documentId=document.manifest.sourceId,
                        sourceName=document.manifest.sourceName,
                        sourceUrl=document.manifest.sourceUrl,
                        sourceType=document.manifest.sourceType,
                        jurisdiction=document.manifest.jurisdiction,
                        licenseClass=document.manifest.licenseClass,
                        language=document.manifest.language,
                        heading=heading,
                        sectionPath=block.section_path or [document.manifest.sourceName],
                        clauseId=block.clause_id,
                        text=child_text,
                        parentChunkId=parent_id,
                        riskTypes=risk_types,
                        evidenceTags=evidence_tags,
                        contentHash=content_hash,
                        tokenCount=token_count,
                        metadata={
                            "blockType": block.block_type,
                            "clauseContext": clause_context,
                            **document.manifest.metadata,
                        },
                    )
                )
                index += 1
        return chunks

    def _blocks(self, markdown: str) -> list[_Block]:
        blocks: list[_Block] = []
        heading_stack: list[str] = []
        current_heading = "root"
        current_clause = ""
        buffer: list[str] = []
        buffer_type = "paragraph"
        table_buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer, buffer_type, table_buffer
            if table_buffer:
                text = "\n".join(table_buffer).strip()
                if text:
                    blocks.append(_Block(text=text, heading=current_heading, section_path=list(heading_stack), clause_id=current_clause, block_type="table"))
                table_buffer = []
            if buffer:
                text = "\n".join(buffer).strip()
                if text:
                    blocks.append(_Block(text=text, heading=current_heading, section_path=list(heading_stack), clause_id=current_clause, block_type=buffer_type))
                buffer = []
                buffer_type = "paragraph"

        for raw_line in markdown.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                # PDFs frequently place a blank line before a page marker while
                # the same legal clause continues on the following page.
                if buffer_type != "clause":
                    flush()
                continue
            if PAGE_MARKER_RE.match(stripped):
                # Page numbers are layout artifacts, not policy evidence.
                continue
            heading_match = HEADING_RE.match(stripped)
            if heading_match:
                flush()
                level = len(heading_match.group(1))
                heading = heading_match.group(2).strip()
                heading_stack = heading_stack[: level - 1] + [heading]
                current_heading = heading
                current_clause = self._clause_id(heading)
                continue
            if TABLE_RE.match(stripped):
                if buffer:
                    flush()
                table_buffer.append(stripped)
                continue
            clause_id = self._clause_id(stripped)
            if clause_id:
                flush()
                current_clause = clause_id
                buffer_type = "clause"
                buffer.append(stripped)
                continue
            if LIST_RE.match(stripped):
                # A numbered/bulleted item is an independent policy unit. If
                # several items share one chunk, a bounded citation can hide
                # the exact rule that justified the decision.
                if buffer:
                    flush()
                buffer_type = "list"
                buffer.append(stripped)
                continue
            if buffer and buffer_type in {"list", "clause"}:
                buffer.append(stripped)
            else:
                buffer_type = "paragraph"
                buffer.append(stripped)
        flush()
        return blocks or [_Block(text=markdown, heading=current_heading, section_path=heading_stack, clause_id=current_clause)]

    def _children(self, text: str, *, clause_context: str = "") -> list[str]:
        # Use the same token contract used by PolicyChunk.tokenCount. A
        # different window tokenizer can silently create nominally 220-token
        # chunks that are much larger once indexed and embedded.
        tokens = COUNT_TOKEN_RE.findall(text)
        if len(tokens) <= self.child_max_tokens:
            return [text.strip()]
        output: list[str] = []
        step = self.child_max_tokens - self.child_overlap_tokens
        for child_index, start in enumerate(range(0, len(tokens), step)):
            window = tokens[start : start + self.child_max_tokens]
            # A final window containing only overlap repeats information that
            # is already present in the previous child.
            if child_index and len(window) <= self.child_overlap_tokens:
                break
            child = self._render_tokens(window).strip()
            if child_index and clause_context:
                child = f"{clause_context}（续）\n{child}"
            output.append(child)
        return [item for item in output if item]

    @staticmethod
    def _render_tokens(tokens: list[str]) -> str:
        """Rebuild fallback windows without splitting Chinese words by spaces."""
        rendered: list[str] = []
        previous = ""
        for token in tokens:
            if not rendered:
                rendered.append(token)
            elif PolicyStructureChunker._needs_separator(previous, token):
                rendered.extend([" ", token])
            else:
                rendered.append(token)
            previous = token
        return "".join(rendered)

    @staticmethod
    def _needs_separator(previous: str, current: str) -> bool:
        if PolicyStructureChunker._is_cjk_token(previous) or PolicyStructureChunker._is_cjk_token(current):
            return False
        if previous in "([{《〈" or current in ",.;:!?%)]}、。，：；！？》〉":
            return False
        return True

    @staticmethod
    def _is_cjk_token(value: str) -> bool:
        return len(value) == 1 and "\u4e00" <= value <= "\u9fff"

    @staticmethod
    def _clause_context(clause_id: str) -> str:
        return f"第{clause_id}条" if clause_id else ""

    @staticmethod
    def _clause_id(text: str) -> str:
        match = CLAUSE_RE.match(text.strip())
        if not match:
            return ""
        return next(group for group in match.groups() if group)

    @staticmethod
    def _risk_types(*parts: str) -> list[str]:
        lowered = " ".join(parts).lower()
        matched = [risk for risk, terms in RISK_KEYWORDS.items() if any(term.lower() in lowered for term in terms)]
        return matched or ["review_policy"]

    @staticmethod
    def _evidence_tags(text: str, risk_types: list[str]) -> list[str]:
        lowered = text.lower()
        tags: list[str] = []
        if any(term in lowered for term in ["paid", "incentive", "cashback", "compensation", "好评返现", "五星截图"]):
            tags.append("incentivized_review")
        if any(term in lowered for term in ["rating", "manipulat", "评分", "操纵"]):
            tags.append("rating_manipulation")
        if any(term in lowered for term in ["fake", "false", "fabricated", "虚假", "刷单", "编造"]):
            tags.append("fake_engagement")
        if any(term in lowered for term in ["delete", "remove", "suppress", "threaten", "删除", "屏蔽", "压制", "差评"]):
            tags.append("review_suppression")
        if any(term in lowered for term in ["privacy", "personal information", "隐私", "个人信息"]):
            tags.append("privacy")
        if any(
            term in lowered
            for term in ["refund", "return", "after-sales", "退款", "退货", "售后", "换货", "修理", "返还", "退还", "价款", "运费"]
        ):
            tags.append("after_sales")
        if any(term in lowered for term in ["fraud", "unsafe", "safety", "欺诈", "假货", "安全"]):
            tags.append("safety_or_fraud")
        return tags or risk_types
