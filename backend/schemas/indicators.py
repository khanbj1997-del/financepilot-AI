"""재무지표·추세 응답 스키마."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class IndicatorPoint(BaseModel):
    period: str
    source: Optional[str] = None
    fs_div: Optional[str] = None
    reprt_code: Optional[str] = None
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    fcf: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    operating_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None
    revenue_growth: Optional[float] = None
    operating_income_growth: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    interest_expense: Optional[float] = None
    currency: Optional[str] = "KRW"
    unit: Optional[str] = "원"
    ratio_unit: Optional[str] = None


class GrowthOut(BaseModel):
    period: str
    revenue_growth: Optional[float] = None
    operating_income_growth: Optional[float] = None
    base_period: Optional[str] = None
    period_label: Optional[str] = None
    base_period_label: Optional[str] = None
    comparison_type: Optional[str] = None
    available: Optional[bool] = None
    unavailable_reason: Optional[str] = None


class IndicatorsResponse(BaseModel):
    company_id: str
    periods: int
    latest: Optional[IndicatorPoint] = None
    growth: Optional[GrowthOut] = None
    trend: list[IndicatorPoint] = Field(default_factory=list)
    message: Optional[str] = None
    notes: dict[str, Any] = Field(
        default_factory=lambda: {
            "roe": "당기순이익 / 자본총계 * 100",
            "roic": "영업이익 / (총자산 - 유동부채) * 100 (MVP 근사)",
            "operating_margin": "영업이익 / 매출 * 100",
            "debt_ratio": "부채총계 / 자본총계 * 100",
            "current_ratio": "유동자산 / 유동부채 * 100",
            "interest_coverage": "영업이익 / 이자비용 (배수)",
            "growth": "전년 동기(동일 Q1/H1/Q3/연간) 대비 증감률 (%). 기간 유형이 다른 값은 비교하지 않음",
        }
    )
