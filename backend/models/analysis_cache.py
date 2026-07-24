"""AI 분석 결과 캐시."""
from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, SQLModel, Text


class AnalysisCache(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("company_id", "cache_key", name="uq_analysis_cache"),
    )

    id: int | None = Field(default=None, primary_key=True)
    company_id: str = Field(index=True, max_length=16)
    cache_key: str = Field(max_length=64, description="입력 데이터 해시")
    source: str = Field(default="openai", max_length=16)
    result_json: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
