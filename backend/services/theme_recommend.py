"""규칙 기반 인기 테마·추천 종목 산출 (시드 + Company.industry).

외부 네이버 데이터랩·KRX는 승인/엔드포인트 검증 전이라 호출하지 않는다.
MarketData 테이블은 향후 연동용으로만 둔다.
테마당 추천 종목은 3~5개를 목표로 시드 이후 DB 업종으로 보강한다.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from sqlmodel import Session, col, delete, func, or_, select

from models.company import Company
from models.theme import Theme, ThemeStock
from services.industry_taxonomy import is_unclassified

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "themes_seed.json"
STOCKS_PER_THEME = 5
MIN_STOCKS_PER_THEME = 3


def _load_seed() -> list[dict]:
    with SEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _industry_counts(session: Session) -> dict[str, int]:
    rows = session.exec(
        select(Company.industry, func.count())
        .where(Company.industry.is_not(None))  # type: ignore[union-attr]
        .group_by(Company.industry)
    ).all()
    out: dict[str, int] = {}
    for industry, cnt in rows:
        if is_unclassified(industry):
            continue
        out[str(industry)] = int(cnt)
    return out


def _companies_by_industries(
    session: Session,
    industries: list[str],
    *,
    exclude: set[str],
    limit: int,
) -> list[Company]:
    if not industries or limit <= 0:
        return []
    cond = or_(*[Company.industry == ind for ind in industries])
    rows = list(
        session.exec(
            select(Company)
            .where(cond)
            .order_by(col(Company.company_name).asc())
            .limit(limit + len(exclude) + 20)
        ).all()
    )
    out: list[Company] = []
    for company in rows:
        if company.company_id in exclude:
            continue
        if is_unclassified(company.industry):
            continue
        out.append(company)
        if len(out) >= limit:
            break
    return out


def rebuild_themes(session: Session) -> dict:
    """시드 테마를 점수 재산출 후 Theme/ThemeStock에 적재한다."""
    seed = _load_seed()
    counts = _industry_counts(session)
    today = date.today()
    now = datetime.utcnow()

    session.exec(delete(ThemeStock))
    session.exec(delete(Theme))
    session.commit()

    theme_n = 0
    stock_n = 0
    for raw in seed:
        industries = [str(x) for x in (raw.get("industries") or [])]
        db_boost = sum(counts.get(ind, 0) for ind in industries)
        score = float(raw.get("base_score") or 50) + min(40.0, db_boost * 0.02)

        theme = Theme(
            theme_id=str(raw["theme_id"]),
            theme_name=str(raw["theme_name"]),
            score=round(score, 2),
            score_date=today,
            description=raw.get("description"),
            source="rule_seed",
            updated_at=now,
        )
        session.add(theme)
        theme_n += 1

        ranked: list[tuple[str, float]] = []
        seen: set[str] = set()
        for item in raw.get("stocks") or []:
            corp = str(item.get("corp_code") or "").strip()
            if not corp or corp in seen:
                continue
            company = session.get(Company, corp)
            if company is None:
                logger.info("테마 종목 스킵(Company 없음): %s", corp)
                continue
            rel = float(item.get("relevance") or 50)
            if company.industry and company.industry in industries:
                rel += 5.0
            ranked.append((corp, rel))
            seen.add(corp)

        need = STOCKS_PER_THEME - len(ranked)
        if need > 0:
            for company in _companies_by_industries(
                session, industries, exclude=seen, limit=need
            ):
                ranked.append((company.company_id, 55.0))
                seen.add(company.company_id)

        ranked.sort(key=lambda x: (-x[1], x[0]))
        ranked = ranked[:STOCKS_PER_THEME]
        for i, (corp, rel) in enumerate(ranked, start=1):
            session.add(
                ThemeStock(
                    theme_id=theme.theme_id,
                    company_id=corp,
                    relevance_score=round(rel, 2),
                    rank=i,
                )
            )
            stock_n += 1

    session.commit()
    logger.info("Theme rebuild: themes=%s stocks=%s", theme_n, stock_n)
    return {"themes": theme_n, "stocks": stock_n, "score_date": today.isoformat()}


def _theme_stock_counts_too_low(session: Session) -> bool:
    themes = list(session.exec(select(Theme)).all())
    if not themes:
        return True
    for theme in themes:
        n = session.exec(
            select(func.count())
            .select_from(ThemeStock)
            .where(ThemeStock.theme_id == theme.theme_id)
        ).one()
        if int(n) < MIN_STOCKS_PER_THEME:
            return True
    return False


def ensure_themes(session: Session) -> dict:
    existing = session.exec(select(func.count()).select_from(Theme)).one()
    if existing and existing > 0 and not _theme_stock_counts_too_low(session):
        return {"status": "ready", "source": "db", "count": int(existing)}
    result = rebuild_themes(session)
    return {"status": "ready", "source": "seed_rule", **result}


def list_themes(session: Session, limit: int = 20) -> list[Theme]:
    limit = max(1, min(limit, 50))
    return list(
        session.exec(
            select(Theme).order_by(col(Theme.score).desc()).limit(limit)
        ).all()
    )


def get_theme(session: Session, theme_id: str) -> Theme | None:
    return session.get(Theme, theme_id)


def list_theme_stocks(
    session: Session, theme_id: str, limit: int = 20
) -> list[tuple[ThemeStock, Company | None]]:
    limit = max(1, min(limit, 50))
    rows = list(
        session.exec(
            select(ThemeStock)
            .where(ThemeStock.theme_id == theme_id)
            .order_by(col(ThemeStock.rank).asc())
            .limit(limit)
        ).all()
    )
    out: list[tuple[ThemeStock, Company | None]] = []
    for row in rows:
        out.append((row, session.get(Company, row.company_id)))
    return out
