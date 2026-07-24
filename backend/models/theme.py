"""인기 테마·테마별 추천 종목·(향후)시장데이터 모델."""
from datetime import date, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Theme(SQLModel, table=True):
    theme_id: str = Field(primary_key=True, max_length=32)
    theme_name: str = Field(max_length=100, index=True)
    score: float = Field(default=0.0)
    score_date: date = Field(default_factory=date.today, index=True)
    description: str | None = Field(default=None, max_length=500)
    # rule_seed | rule_db — 실시간 시장/검색 API가 아님을 구분
    source: str = Field(default="rule_seed", max_length=32)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ThemeStock(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("theme_id", "company_id", name="uq_theme_stock"),
    )

    id: int | None = Field(default=None, primary_key=True)
    theme_id: str = Field(index=True, max_length=32)
    company_id: str = Field(index=True, max_length=16)
    relevance_score: float = Field(default=0.0)
    rank: int = Field(default=0)


class MarketData(SQLModel, table=True):
    """KRX 등 시장데이터 연동 시 사용. 현재 B3에서는 적재하지 않음."""

    __table_args__ = (
        UniqueConstraint("company_id", "trade_date", name="uq_market_data_day"),
    )

    id: int | None = Field(default=None, primary_key=True)
    company_id: str = Field(index=True, max_length=16)
    trade_date: date = Field(index=True, description="PRD MarketData.date")
    volume: float | None = Field(default=None)
    trading_value: float | None = Field(default=None)
