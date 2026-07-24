"""Dashboard 통합 응답 스키마."""
from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.analysis import AnalysisResult
from schemas.company import CompanyOut
from schemas.financial import FinancialPeriodOut
from schemas.indicators import GrowthOut, IndicatorPoint
from schemas.industry import IndustryProfileOut


class DashboardSectionStatus(BaseModel):
    company: bool = False
    financials: bool = False
    indicators: bool = False
    industry: bool = False
    analysis: bool = False


class DashboardResponse(BaseModel):
    company_id: str
    company: Optional[CompanyOut] = None
    financials: list[FinancialPeriodOut] = Field(default_factory=list)
    indicators: Optional[IndicatorPoint] = None
    growth: Optional[GrowthOut] = None
    trend: list[IndicatorPoint] = Field(default_factory=list)
    trend_quarterly: list[IndicatorPoint] = Field(default_factory=list)
    industry_profile: Optional[IndustryProfileOut] = None
    analysis: Optional[AnalysisResult] = None
    analysis_source: Optional[str] = None
    analysis_cached: bool = False
    sections: DashboardSectionStatus = Field(default_factory=DashboardSectionStatus)
    warnings: list[str] = Field(default_factory=list)  # 실패/경고만
    notices: list[str] = Field(default_factory=list)  # 안내(rule 모드 등)
    message: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
