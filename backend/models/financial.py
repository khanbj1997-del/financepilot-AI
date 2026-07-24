"""재무 데이터 SQLModel."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, SQLModel, Text


class FinancialData(SQLModel, table=True):
    """기간별 정제된 재무 지표 (company_id + period 기준)."""

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "period",
            "reprt_code",
            "fs_div",
            name="uq_financial_period",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: str = Field(index=True, max_length=16)
    period: str = Field(index=True, max_length=8, description="기간 예: 2024, 2025Q3")
    reprt_code: str = Field(default="11011", max_length=5)
    fs_div: str = Field(default="CFS", max_length=3)
    source: str = Field(default="seed", max_length=16)
    metrics_json: str = Field(sa_column=Column(Text))
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
