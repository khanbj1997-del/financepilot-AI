"""즐겨찾기 API — user_id는 항상 local."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from database import get_session
from schemas.company import CompanyOut
from schemas.favorite import (
    FavoriteListResponse,
    FavoriteMutationResponse,
    FavoriteOut,
    FavoriteStatusOut,
)
from services import favorites as fav_svc

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=FavoriteListResponse)
def get_favorites(session: Session = Depends(get_session)):
    pairs = fav_svc.list_favorites(session)
    items: list[FavoriteOut] = []
    for fav, company in pairs:
        items.append(
            FavoriteOut(
                user_id=fav.user_id,
                company_id=fav.company_id,
                created_at=fav.created_at,
                company=CompanyOut.model_validate(company) if company else None,
            )
        )
    return FavoriteListResponse(
        user_id=fav_svc.LOCAL_USER_ID,
        total=len(items),
        items=items,
    )


@router.get("/{company_id}/status", response_model=FavoriteStatusOut)
def get_favorite_status(company_id: str, session: Session = Depends(get_session)):
    return FavoriteStatusOut(
        user_id=fav_svc.LOCAL_USER_ID,
        company_id=company_id,
        is_favorite=fav_svc.is_favorite(session, company_id),
    )


@router.post("/{company_id}", response_model=FavoriteMutationResponse)
def add_favorite(company_id: str, session: Session = Depends(get_session)):
    try:
        fav_svc.add_favorite(session, company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FavoriteMutationResponse(
        user_id=fav_svc.LOCAL_USER_ID,
        company_id=company_id,
        is_favorite=True,
        message="즐겨찾기에 추가했습니다.",
    )


@router.delete("/{company_id}", response_model=FavoriteMutationResponse)
def remove_favorite(company_id: str, session: Session = Depends(get_session)):
    removed = fav_svc.remove_favorite(session, company_id)
    return FavoriteMutationResponse(
        user_id=fav_svc.LOCAL_USER_ID,
        company_id=company_id,
        is_favorite=False,
        message=(
            "즐겨찾기에서 제거했습니다."
            if removed
            else "즐겨찾기에 없는 기업입니다."
        ),
    )
