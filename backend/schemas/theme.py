"""테마·추천 API 스키마."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.company import CompanyOut


class ThemeOut(BaseModel):
    theme_id: str
    theme_name: str
    score: float
    score_date: date
    description: Optional[str] = None
    source: str = "rule_seed"
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ThemeStockOut(BaseModel):
    theme_id: str
    company_id: str
    relevance_score: float
    rank: int
    company: Optional[CompanyOut] = None


class ThemeListResponse(BaseModel):
    total: int
    items: list[ThemeOut] = Field(default_factory=list)
    message: str = (
        "DB 업종·시드 기반 규칙 추천입니다. "
        "실시간 검색관심도(네이버)·거래량(KRX)은 미연동입니다."
    )


class ThemeStocksResponse(BaseModel):
    theme: ThemeOut
    total: int
    items: list[ThemeStockOut] = Field(default_factory=list)
    message: str = "추천 종목의 company_id로 기존 분석 Dashboard를 사용하세요."
