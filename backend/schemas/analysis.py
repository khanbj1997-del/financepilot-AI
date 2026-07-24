"""AI 종합 재무 분석 응답 스키마."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class KeyQuestion(BaseModel):
    question: str
    why: str


class AnalysisResult(BaseModel):
    """투자 의사결정 보조용 구조화 분석 (원본 수치와 구분)."""

    overall_judgment: str = Field(description="종합 판단 3~5문장")
    key_variable: str = Field(description="현재 가장 중요한 핵심 변수 1개")
    financial_soundness: str = Field(description="재무 건전성 해석")
    profitability: str = Field(description="수익성 해석")
    growth: str = Field(description="성장성 해석")
    earnings_quality: str = Field(description="이익의 질 해석")
    strengths: list[str] = Field(default_factory=list, description="주요 강점 최대 3개")
    risks: list[str] = Field(default_factory=list, description="주요 위험요인 최대 3개")
    key_questions: list[KeyQuestion] = Field(
        default_factory=list, description="가장 중요한 투자 질문 최대 3개"
    )
    data_to_watch: list[str] = Field(
        default_factory=list, description="앞으로 확인할 데이터"
    )
    data_as_of: Optional[str] = None
    disclaimer: str = (
        "본 분석은 제공된 재무 수치에 근거한 참고용 해석이며 투자 권유가 아닙니다. "
        "없는 사실은 생성하지 않으며, 매수·매도 의견을 제시하지 않습니다."
    )


class AnalysisResponse(BaseModel):
    company_id: str
    company_name: str
    industry: Optional[str] = None
    source: str
    cached: bool = False
    analysis: AnalysisResult
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None  # 실패/경고
    notice: Optional[str] = None  # 안내
