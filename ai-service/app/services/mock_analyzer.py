import json
import math
from pathlib import Path
from typing import Dict, List

from app.core.config import settings
from app.schemas.review import ReviewAnalyzeRequest, SimilarCase
from app.services.base import AnalyzerBase


POSITIVE_WORDS = ["\u597d", "\u4e0d\u9519", "\u6ee1\u610f", "\u559c\u6b22", "\u8212\u670d", "\u6f02\u4eae", "\u8d28\u91cf", "\u63a8\u8350"]
NEGATIVE_WORDS = ["\u5dee", "\u574f", "\u5931\u671b", "\u96be\u7528", "\u4e00\u822c", "\u6307\u7eb9", "\u77ed", "\u6162", "\u5f02\u5473"]
RISK_WORDS = ["\u5047\u8d27", "\u7834\u635f", "\u9000\u6b3e", "\u6295\u8bc9", "\u6b3a\u9a97", "\u5b89\u5168", "\u7206\u70b8", "\u8fc7\u654f", "\u552e\u540e", "\u9000\u8d27"]


class MockAnalyzer(AnalyzerBase):
    def analyze_text(self, payload: ReviewAnalyzeRequest) -> Dict:
        text = payload.review_text or ""
        positive_hits = [word for word in POSITIVE_WORDS if word in text]
        negative_hits = [word for word in NEGATIVE_WORDS if word in text]
        risk_hits = [word for word in RISK_WORDS if word in text]

        rating_score = 0.6 if payload.rating is None else payload.rating / 5
        lexical_score = 0.5 + 0.08 * len(positive_hits) - 0.1 * len(negative_hits)
        text_score = max(0.05, min(0.98, (rating_score + lexical_score) / 2))

        if text_score >= 0.68 and len(negative_hits) <= 1:
            label = "positive"
        elif text_score <= 0.42 or len(risk_hits) > 0:
            label = "negative"
        else:
            label = "neutral"

        evidence = positive_hits + negative_hits + risk_hits
        if not evidence:
            evidence = [text[:20]] if text else ["empty review text"]

        return {
            "sentiment_label": label,
            "text_score": round(text_score, 4),
            "confidence": round(min(0.95, 0.68 + 0.05 * len(evidence)), 4),
            "text_evidence": evidence[:5],
            "risk_hits": risk_hits,
        }

    def analyze_images(self, image_urls: List[str]) -> Dict:
        if not image_urls:
            return {
                "image_score": 0.5,
                "image_evidence": ["\u672a\u63d0\u4f9b\u56fe\u7247\uff0c\u4f7f\u7528\u6587\u672c\u7ed3\u679c\u4e3a\u4e3b"],
            }

        valid_count = sum(1 for url in image_urls if url.startswith("http://") or url.startswith("https://"))
        score = 0.64 + min(valid_count, 3) * 0.04
        evidence = ["\u5546\u54c1\u5916\u89c2\u4fe1\u606f\u5df2\u5b8c\u6210\u5360\u4f4d\u89e3\u6790"]
        if valid_count < len(image_urls):
            evidence.append("\u5b58\u5728\u975e HTTP \u56fe\u7247 URL\uff0c\u5df2\u964d\u4f4e\u56fe\u50cf\u7f6e\u4fe1\u5ea6")
            score -= 0.08

        return {
            "image_score": round(max(0.2, min(0.9, score)), 4),
            "image_evidence": evidence,
        }

    def retrieve_similar_cases(self, payload: ReviewAnalyzeRequest) -> List[SimilarCase]:
        cases = self._load_cases()
        if not cases:
            return [
                SimilarCase(
                    case_id="LOCAL-FALLBACK-CASE",
                    review_text=(payload.review_text or "")[:120],
                    sentiment_label="neutral",
                    similarity=0.5,
                    label="neutral",
                    reason="local case memory is empty; fallback case preserves API response shape",
                )
            ]
        scored_cases = []
        for item in cases:
            similarity = self._simple_similarity(payload.review_text, item.get("review_text", ""))
            scored_cases.append((similarity, item))

        scored_cases.sort(key=lambda row: row[0], reverse=True)
        return [
            SimilarCase(
                case_id=item.get("case_id", "C000"),
                review_text=item.get("review_text", ""),
                sentiment_label=item.get("sentiment_label", "neutral"),
                similarity=round(max(score, 0.5), 4),
                label=item.get("sentiment_label", "neutral"),
                reason=item.get("review_text", "")[:80],
            )
            for score, item in scored_cases[:3]
        ]

    def _load_cases(self) -> List[Dict]:
        path = Path(settings.cases_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig") as file:
            return json.load(file)

    def _simple_similarity(self, left: str, right: str) -> float:
        left_chars = set(left or "")
        right_chars = set(right or "")
        if not left_chars or not right_chars:
            return 0.5
        overlap = len(left_chars & right_chars)
        union = len(left_chars | right_chars)
        return 0.5 + 0.45 * math.sqrt(overlap / union)
