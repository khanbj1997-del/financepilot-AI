"""즐겨찾기 추가·제거·목록 (user_id=local 고정)."""
from __future__ import annotations

from sqlmodel import Session, col, select

from models.company import Company
from models.favorite import Favorite

LOCAL_USER_ID = "local"


def is_favorite(session: Session, company_id: str, user_id: str = LOCAL_USER_ID) -> bool:
    row = session.exec(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.company_id == company_id,
        )
    ).first()
    return row is not None


def add_favorite(
    session: Session,
    company_id: str,
    user_id: str = LOCAL_USER_ID,
) -> Favorite:
    company = session.get(Company, company_id)
    if company is None:
        raise LookupError("기업을 찾을 수 없습니다.")

    existing = session.exec(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.company_id == company_id,
        )
    ).first()
    if existing is not None:
        return existing

    row = Favorite(user_id=user_id, company_id=company_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def remove_favorite(
    session: Session,
    company_id: str,
    user_id: str = LOCAL_USER_ID,
) -> bool:
    """제거했으면 True, 원래 없었으면 False."""
    row = session.exec(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.company_id == company_id,
        )
    ).first()
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


def list_favorites(
    session: Session,
    user_id: str = LOCAL_USER_ID,
) -> list[tuple[Favorite, Company | None]]:
    rows = list(
        session.exec(
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .order_by(col(Favorite.created_at).desc())
        ).all()
    )
    out: list[tuple[Favorite, Company | None]] = []
    for fav in rows:
        company = session.get(Company, fav.company_id)
        out.append((fav, company))
    return out
