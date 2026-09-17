from __future__ import annotations

"""Conservative multilingual input gate for review-governance requests."""

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from app.runtime.input_gate_models import LocalDuoGuardScanner, MultilingualPrototypeClassifier


CONTINUE_REVIEW = "continue_review"
INPUT_GUIDANCE = "input_guidance"

_SEPARATOR_RE = re.compile(r"[\s,.!?，。！？、~～…·:：;；'\"“”‘’（）()\[\]【】]+")
_SEMANTIC_TEXT_RE = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_GREETING_RE = re.compile(
    r"^(?:(?:你|您)?好(?:啊|呀|哇|哦|哟|呢|吗|嘛|哈|喽)*|嗨(?:呀|啊|哟)*|哈[喽啰](?:呀|啊|哟)*|"
    r"hello|hi|hey|こんにちは|こんばんは|おはよう|안녕|안녕하세요)$",
    re.IGNORECASE,
)
_CONVERSATION_RE = re.compile(
    r"^(?:在吗|有人吗|你是谁|你是做什么的|干嘛呢|讲个笑话|陪我聊天|测试一下|试试看|test|help|帮助|怎么用|"
    r"谢谢|多谢|thankyou|thanks|今天天气怎么样|今天星期几|写首诗)$",
    re.IGNORECASE,
)
_FILLER_RE = re.compile(r"^(?:哈{2,}|呵{2,}|嘿{2,}|嗯{2,}|哦{2,}|额{2,})$")
_SHORT_REVIEW_SIGNAL_RE = re.compile(
    r"^(?:差|不好|太差|坏了|坏掉了|很烫|太烫|发烫|被骗|被骗了|有问题|有毛病|删评|删评价|删除评价)$"
)
_INJECTION_CUE_RE = re.compile(
    r"ignore|instruction|system prompt|developer message|jailbreak|忽略|指令|系统提示|提示词|越狱|"
    r"指示を無視|システムプロンプト|지시를 무시|시스템 프롬프트",
    re.IGNORECASE,
)
_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)",
        r"(?:reveal|show|print|repeat)\s+(?:the\s+)?(?:system|developer)\s+(?:prompt|message|instructions?)",
        r"(?:mark|classify|label)\s+(?:this\s+)?(?:review\s+)?(?:as\s+)?safe",
        r"忽略(?:之前|以上|上面|所有)?(?:的)?(?:指令|提示词|要求)",
        r"(?:显示|输出|泄露|告诉我)(?:系统|开发者)?(?:提示词|指令)",
        r"(?:把|将)?(?:这条)?(?:评论)?(?:判定|标记|分类)(?:为|成)?(?:安全|无风险)",
        r"前の指示を無視[^。.!！]*",
        r"システムプロンプト(?:を)?(?:表示|公開|出力)[^。.!！]*",
        r"이전\s*지시를\s*무시[^.!。！]*",
        r"시스템\s*프롬프트(?:를)?\s*(?:보여|출력|공개)[^.!。！]*",
    )
)
_BUSINESS_SIGNAL_RE = re.compile(
    r"退款|退货|售后|破损|返现|五星|刷单|虚假评价|删除差评|屏蔽评价|"
    r"电池|电芯|充电|鼓包|膨胀|发烫|过热|漏液|冒烟|起火|爆炸|隐私|威胁|骚扰|"
    r"refund|return|cashback|fake review|delete review|rating manipulation|battery|charging|swollen|"
    r"overheat|smoke|fire|explode|exploded|privacy|threat|harass|"
    r"返品|返金|レビュー操作|偽レビュー|電池|バッテリー|膨張|発熱|煙|発火|爆発|"
    r"환불|반품|가짜 리뷰|평점 조작|배터리|부풀|과열|연기|화재|폭발",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReviewInputGateDecision:
    decision: str
    reasonCode: str
    message: str
    category: str = "REVIEW"
    confidence: float = 1.0
    provider: str = "deterministic"
    securityFlags: list[str] = field(default_factory=list)
    restrictedMode: bool = False
    processingText: str = ""
    normalizedChanged: bool = False
    modelDetails: dict[str, Any] = field(default_factory=dict)

    @property
    def should_continue(self) -> bool:
        return self.decision == CONTINUE_REVIEW

    def metadata(self) -> dict[str, Any]:
        values = asdict(self)
        values.pop("processingText", None)
        values["skipModelEnhancement"] = not self.should_continue or self.restrictedMode
        return values


class ReviewInputGate:
    """Filter only proven non-review input; uncertainty always enters the long path."""

    def __init__(self, *, semantic_classifier: Any = None, injection_scanner: Any = None) -> None:
        self.semantic_classifier = semantic_classifier or MultilingualPrototypeClassifier()
        self.injection_scanner = injection_scanner or LocalDuoGuardScanner()

    def evaluate(self, text: str) -> ReviewInputGateDecision:
        original = text or ""
        normalized = self._normalize(original)
        compact = _SEPARATOR_RE.sub("", normalized.lower())
        if not compact or not _SEMANTIC_TEXT_RE.search(compact):
            return self._guidance("NON_SEMANTIC_INPUT", "当前输入不包含可审核的评论内容，请补充商品体验或具体治理问题。", normalized)

        deterministic_injection = any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS)
        sanitized = self._sanitize_injection(normalized) if deterministic_injection else normalized
        guard = None
        if deterministic_injection or _INJECTION_CUE_RE.search(normalized):
            guard = self.injection_scanner.scan(normalized)
        injection_detected = deterministic_injection or bool(guard and guard.detected)
        has_business_signal = bool(_BUSINESS_SIGNAL_RE.search(sanitized))
        guard_details = {
            "guardProvider": getattr(guard, "provider", "not_invoked"),
            "guardScore": float(getattr(guard, "score", 0.0)),
            "guardStatus": getattr(guard, "status", "not_invoked"),
        }

        if injection_detected and has_business_signal:
            return ReviewInputGateDecision(
                CONTINUE_REVIEW,
                "PROMPT_INJECTION_WITH_BUSINESS_SIGNAL",
                "已忽略疑似攻击指令，并保留真实商品或安全风险进入受限审核链路。",
                category="GOVERNANCE_QUERY",
                provider="deterministic_plus_guard",
                securityFlags=["PROMPT_INJECTION_DETECTED", "BUSINESS_SIGNAL_PRESERVED"],
                restrictedMode=True,
                processingText=sanitized,
                normalizedChanged=sanitized != original,
                modelDetails=guard_details,
            )
        if injection_detected:
            return self._guidance(
                "PROMPT_INJECTION_BLOCKED",
                "检测到与评论审核无关的指令性内容，未进入治理流程。请只描述真实商品体验或治理问题。",
                sanitized,
                category="PROMPT_INJECTION",
                provider="deterministic_plus_guard",
                security_flags=["PROMPT_INJECTION_DETECTED"],
                model_details=guard_details,
            )
        if has_business_signal:
            return ReviewInputGateDecision(
                CONTINUE_REVIEW,
                "BUSINESS_SIGNAL_PRESENT",
                "输入包含商品、售后或安全相关事实，继续执行评论治理。",
                processingText=normalized,
                normalizedChanged=normalized != original,
            )
        if _GREETING_RE.fullmatch(compact):
            return self._guidance("CONVERSATIONAL_GREETING", "这是问候语，不属于需要审核的评论，请补充商品体验或具体治理问题。", normalized)
        if _CONVERSATION_RE.fullmatch(compact) or _FILLER_RE.fullmatch(compact):
            return self._guidance("CONVERSATIONAL_OR_OUT_OF_SCOPE", "当前输入属于闲聊或使用咨询，不进入评论治理和人工复核。", normalized)
        if _SHORT_REVIEW_SIGNAL_RE.fullmatch(compact):
            return ReviewInputGateDecision(
                CONTINUE_REVIEW,
                "SHORT_REVIEW_SIGNAL_LONG_PATH",
                "输入较短但包含负面体验或治理信号，按安全默认进入完整审核。",
                category="REVIEW",
                confidence=1.0,
                provider="deterministic",
                processingText=normalized,
                normalizedChanged=normalized != original,
            )

        semantic = self.semantic_classifier.classify(normalized)
        category = str(getattr(semantic, "category", "UNCERTAIN")).upper()
        confidence = float(getattr(semantic, "confidence", 0.0))
        provider = str(getattr(semantic, "provider", "semantic_unavailable"))
        details = {"semanticScores": getattr(semantic, "scores", {})}
        if category in {"CHAT", "OUT_OF_SCOPE", "GIBBERISH"} and confidence >= 0.72:
            return self._guidance(
                f"SEMANTIC_{category}",
                "当前输入与商品评论治理无关，不进入审核流程。请补充具体商品体验或风险事实。",
                normalized,
                category=category,
                confidence=confidence,
                provider=provider,
                model_details=details,
            )
        if category in {"REVIEW", "GOVERNANCE_QUERY"} and confidence >= 0.60:
            return ReviewInputGateDecision(
                CONTINUE_REVIEW,
                "SEMANTIC_REVIEW_INPUT",
                "输入语义与商品评论或治理问题相关，继续执行审核。",
                category=category,
                confidence=confidence,
                provider=provider,
                processingText=normalized,
                normalizedChanged=normalized != original,
                modelDetails=details,
            )
        return ReviewInputGateDecision(
            CONTINUE_REVIEW,
            "SEMANTIC_UNCERTAIN_LONG_PATH",
            "当前输入无法明确证明为无风险闲聊，按安全默认进入完整审核链路。",
            category="UNCERTAIN",
            confidence=confidence,
            provider=provider,
            processingText=normalized,
            normalizedChanged=normalized != original,
            modelDetails=details,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).strip()
        return "".join(char for char in normalized if not unicodedata.category(char).startswith("C"))

    @staticmethod
    def _sanitize_injection(value: str) -> str:
        sanitized = value
        for pattern in _INJECTION_PATTERNS:
            sanitized = pattern.sub(" ", sanitized)
        return " ".join(sanitized.split()).strip(" ,.;，。；")

    @staticmethod
    def _guidance(
        reason: str,
        message: str,
        processing_text: str,
        *,
        category: str = "NON_REVIEW",
        confidence: float = 1.0,
        provider: str = "deterministic",
        security_flags: list[str] | None = None,
        model_details: dict[str, Any] | None = None,
    ) -> ReviewInputGateDecision:
        return ReviewInputGateDecision(
            INPUT_GUIDANCE,
            reason,
            message,
            category=category,
            confidence=confidence,
            provider=provider,
            securityFlags=security_flags or [],
            processingText=processing_text,
            modelDetails=model_details or {},
        )
