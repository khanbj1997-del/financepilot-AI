"""기업 검색·기본정보 응답 스키마."""
from typing import Optional

from pydantic import BaseModel, Field


class CompanyOut(BaseModel):
    company_id: str
    company_name: str
    stock_code: Optional[str] = None
    corp_code: str
    industry: Optional[str] = None

    model_config = {"from_attributes": True}


class CompanySearchResponse(BaseModel):
    query: str
    total: int
    items: list[CompanyOut] = Field(default_factory=list)
