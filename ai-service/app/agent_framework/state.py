from typing import Any, Dict, List, Optional, TypedDict

from app.schemas.review import ReviewAnalyzeRequest, SimilarCase


class AgentState(TypedDict, total=False):
    payload: ReviewAnalyzeRequest
    review_id: str
    product_id: str
    product_name: str
    rating: Optional[int]
    review_text: str
    image_url: Optional[str]
    text_signal: Dict[str, Any]
    image_signal: Dict[str, Any]
    rating_signal: Dict[str, Any]
    sentiment_label: str
    confidence: float
    modality_conflict_score: float
    modality_conflict: Dict[str, Any]
    dominant_modality: Dict[str, Any]
    risk_types: List[str]
    risk_level: str
    evidence: List[str]
    similar_cases: List[SimilarCase]
    suggestions: Dict[str, Any]
    trace_steps: List[Dict[str, Any]]
    fallback_used: bool
    error_message: Optional[str]
