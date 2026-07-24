"""기업(Company) SQLModel."""
from typing import Optional

from sqlmodel import Field, SQLModel


class Company(SQLModel, table=True):
    """Company Master — 모든 분석의 기준 식별자."""

    company_id: str = Field(primary_key=True, max_length=16, description="내부 ID (= corp_code)")
    company_name: str = Field(index=True, max_length=200)
    stock_code: Optional[str] = Field(default=None, index=True, max_length=10)
    corp_code: str = Field(index=True, max_length=8, unique=True)
    industry: Optional[str] = Field(default=None, max_length=100)
    # dart | seed | groq | unknown | unresolved
    industry_source: Optional[str] = Field(default=None, max_length=20)
    industry_confidence: Optional[float] = Field(default=None)
    industry_updated_at: Optional[str] = Field(default=None, max_length=32)
