"""인기 테마·테마별 추천 기업 API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from database import get_session
from schemas.company import CompanyOut
from schemas.theme import (
    ThemeListResponse,
    ThemeOut,
    ThemeStockOut,
    ThemeStocksResponse,
)
from services import theme_recommend as tr

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("", response_model=ThemeListResponse)
def get_themes(
    limit: int = Query(20, ge=1, le=50),
    refresh: bool = Query(False, description="true면 시드·규칙으로 재산출"),
    session: Session = Depends(get_session),
):
    if refresh:
        tr.rebuild_themes(session)
    else:
        tr.ensure_themes(session)
    items = [ThemeOut.model_validate(t) for t in tr.list_themes(session, limit=limit)]
    return ThemeListResponse(total=len(items), items=items)


@router.post("/rebuild")
def rebuild_themes(session: Session = Depends(get_session)):
    result = tr.rebuild_themes(session)
    return {"status": "ok", **result}


@router.get("/{theme_id}/stocks", response_model=ThemeStocksResponse)
def get_theme_stocks(
    theme_id: str,
    limit: int = Query(5, ge=1, le=50),
    session: Session = Depends(get_session),
):
    tr.ensure_themes(session)
    theme = tr.get_theme(session, theme_id)
    if theme is None:
        raise HTTPException(status_code=404, detail="테마를 찾을 수 없습니다.")
    pairs = tr.list_theme_stocks(session, theme_id, limit=limit)
    items = [
        ThemeStockOut(
            theme_id=row.theme_id,
            company_id=row.company_id,
            relevance_score=row.relevance_score,
            rank=row.rank,
            company=CompanyOut.model_validate(company) if company else None,
        )
        for row, company in pairs
    ]
    return ThemeStocksResponse(
        theme=ThemeOut.model_validate(theme),
        total=len(items),
        items=items,
    )


@router.get("/{theme_id}", response_model=ThemeOut)
def get_theme(theme_id: str, session: Session = Depends(get_session)):
    tr.ensure_themes(session)
    theme = tr.get_theme(session, theme_id)
    if theme is None:
        raise HTTPException(status_code=404, detail="테마를 찾을 수 없습니다.")
    return ThemeOut.model_validate(theme)
