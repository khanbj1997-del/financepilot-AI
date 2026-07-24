"""업종 특성 참고 데이터 스키마."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class IndustryProfileOut(BaseModel):
    industry: str
    profile_key: str
    matched: bool
    capital_intensity: Optional[str] = None
    revenue_structure: Optional[str] = None
    liquidity_note: Optional[str] = None
    profitability_note: Optional[str] = None
    metric_hints: dict[str, Any] = Field(default_factory=dict)
    analysis_rules: list[str] = Field(default_factory=list)
    requested_industry: Optional[str] = None


class IndustryListResponse(BaseModel):
    total: int
    items: list[str]


class IndustryContextResponse(BaseModel):
    company_id: str
    company_name: str
    industry: Optional[str] = None
    profile: IndustryProfileOut
    indicators_latest: Optional[dict[str, Any]] = None
    indicators_growth: Optional[dict[str, Any]] = None
    trend_periods: list[str] = Field(default_factory=list)
    prompt_hints: dict[str, Any] = Field(default_factory=dict)
    prompt_text: str
    message: Optional[str] = None
