from abc import ABC, abstractmethod
from typing import Dict, List

from app.schemas.review import ReviewAnalyzeRequest, SimilarCase


class AnalyzerBase(ABC):
    @abstractmethod
    def analyze_text(self, payload: ReviewAnalyzeRequest) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def analyze_images(self, image_urls: List[str]) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def retrieve_similar_cases(self, payload: ReviewAnalyzeRequest) -> List[SimilarCase]:
        raise NotImplementedError


class AgentWorkflowBase(ABC):
    @abstractmethod
    def run(self, payload: ReviewAnalyzeRequest):
        raise NotImplementedError


class RealMultimodalAnalyzer(AnalyzerBase):
    def analyze_text(self, payload: ReviewAnalyzeRequest) -> Dict:
        raise NotImplementedError("Reserved for a real multimodal sentiment model.")

    def analyze_images(self, image_urls: List[str]) -> Dict:
        raise NotImplementedError("Reserved for image understanding models.")

    def retrieve_similar_cases(self, payload: ReviewAnalyzeRequest) -> List[SimilarCase]:
        raise NotImplementedError("Reserved for vector retrieval such as Qdrant.")


class LangGraphAgentWorkflow(AgentWorkflowBase):
    def run(self, payload: ReviewAnalyzeRequest):
        raise NotImplementedError("Reserved for a LangGraph workflow implementation.")
