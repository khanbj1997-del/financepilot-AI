"""즐겨찾기 API 스키마."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.company import CompanyOut


class FavoriteOut(BaseModel):
    user_id: str
    company_id: str
    created_at: datetime
    company: Optional[CompanyOut] = None

    model_config = {"from_attributes": True}


class FavoriteStatusOut(BaseModel):
    user_id: str
    company_id: str
    is_favorite: bool


class FavoriteListResponse(BaseModel):
    user_id: str
    total: int
    items: list[FavoriteOut] = Field(default_factory=list)


class FavoriteMutationResponse(BaseModel):
    user_id: str
    company_id: str
    is_favorite: bool
    message: str
