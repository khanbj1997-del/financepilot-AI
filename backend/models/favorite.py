"""즐겨찾기(Favorite) SQLModel — 단일 로컬 사용자."""
from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Favorite(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_favorite_user_company"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(default="local", index=True, max_length=32)
    company_id: str = Field(index=True, max_length=16)
    created_at: datetime = Field(default_factory=datetime.utcnow)
