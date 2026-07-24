"""재무 데이터 응답 스키마."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FinancialPeriodOut(BaseModel):
    company_id: str
    period: str
    reprt_code: str
    fs_div: str
    source: str
    metrics: dict[str, Any]
    fetched_at: datetime


class FinancialListResponse(BaseModel):
    company_id: str
    total: int
    items: list[FinancialPeriodOut] = Field(default_factory=list)
    message: Optional[str] = None
