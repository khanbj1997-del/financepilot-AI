"""Company Master 적재·검색·조회."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, col, func, select

from models.analysis_cache import AnalysisCache
from models.company import Company
from models.financial import FinancialData
from services.dart_corp_code import DartCorpCodeError, fetch_listed_companies_from_dart
from services.industry_taxonomy import is_unclassified, normalize_industry

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "companies_seed.json"
# seed 수준이면 DART 전체 상장사로 업그레이드 시도
SEED_THRESHOLD = 50


def count_companies(session: Session) -> int:
    return session.exec(select(func.count()).select_from(Company)).one()


def _classified_industry(value: object) -> str | None:
    """저장 가능한 정상 업종만 반환. 미분류/빈값은 None."""
    return normalize_industry(str(value) if value is not None else None)


def dedupe_listed_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """
    동일 기업명·동일 종목코드 중복을 제거한다.

    DART corpCode에는 합병·재상장 등으로 같은 이름에 옛 corp가 남는 경우가 있다.
    modify_date가 최신인 행만 남긴다. 반환: (유지 목록, 제외 corp_code 목록)
    """
    by_name: dict[str, dict] = {}
    for row in rows:
        name = (row.get("company_name") or "").strip()
        if not name:
            continue
        prev = by_name.get(name)
        if prev is None or (row.get("modify_date") or "") > (prev.get("modify_date") or ""):
            by_name[name] = row

    by_stock: dict[str, dict] = {}
    for row in by_name.values():
        stock = (row.get("stock_code") or "").strip()
        if not stock:
            continue
        prev = by_stock.get(stock)
        if prev is None or (row.get("modify_date") or "") > (prev.get("modify_date") or ""):
            by_stock[stock] = row

    kept = list(by_stock.values())
    kept_ids = {str(r["corp_code"]).strip() for r in kept}
    dropped = [
        str(r["corp_code"]).strip()
        for r in rows
        if str(r["corp_code"]).strip() not in kept_ids
    ]
    return kept, dropped


def _delete_company_and_related(session: Session, company_id: str) -> None:
    for row in session.exec(
        select(FinancialData).where(FinancialData.company_id == company_id)
    ).all():
        session.delete(row)
    for row in session.exec(
        select(AnalysisCache).where(AnalysisCache.company_id == company_id)
    ).all():
        session.delete(row)
    company = session.get(Company, company_id)
    if company is not None:
        session.delete(company)


def prune_companies_not_in(session: Session, keep_corp_codes: set[str]) -> int:
    """keep 집합에 없는 Company(및 관련 재무·분석 캐시)를 삭제. 반환: 삭제 건수."""
    if not keep_corp_codes:
        return 0
    removed = 0
    for company in list(session.exec(select(Company)).all()):
        if company.company_id in keep_corp_codes:
            continue
        _delete_company_and_related(session, company.company_id)
        removed += 1
        if removed % 200 == 0:
            session.commit()
    session.commit()
    return removed


def upsert_companies(
    session: Session,
    rows: list[dict],
    commit_every: int = 500,
    *,
    industry_source: str | None = None,
) -> int:
    """
    corp_code 기준으로 삽입/갱신. 반환: 처리 건수.

    industry는 정상 분류값일 때만 반영한다.
    '미분류'/빈값은 기존 정상 업종을 덮어쓰지 않는다.
    """
    n = 0
    now = datetime.utcnow().isoformat(timespec="seconds")
    for row in rows:
        corp_code = str(row["corp_code"]).strip()
        stock = row.get("stock_code")
        stock_code = str(stock).strip().zfill(6) if stock else None
        incoming = _classified_industry(row.get("industry")) if "industry" in row else None
        source = industry_source or row.get("industry_source")
        company = session.get(Company, corp_code)
        if company is None:
            company = Company(
                company_id=corp_code,
                company_name=row["company_name"].strip(),
                stock_code=stock_code,
                corp_code=corp_code,
                industry=incoming,
                industry_source=(source if incoming else None),
                industry_confidence=(1.0 if incoming and source in {"seed", "dart"} else None),
                industry_updated_at=(now if incoming else None),
            )
            session.add(company)
        else:
            company.company_name = row["company_name"].strip()
            company.stock_code = stock_code
            # 정상 업종만 갱신. 기존이 정상이면 미분류로 덮지 않음.
            if incoming and (
                is_unclassified(company.industry) or company.industry != incoming
            ):
                # DART/seed가 groq 추정보다 우선. groq만 있는 경우 seed/dart로 교체 허용.
                if company.industry_source == "dart" and source not in {"dart", "seed"}:
                    pass
                else:
                    company.industry = incoming
                    if source:
                        company.industry_source = source
                    company.industry_confidence = (
                        1.0 if source in {"seed", "dart"} else company.industry_confidence
                    )
                    company.industry_updated_at = now
        n += 1
        if n % commit_every == 0:
            session.commit()
    session.commit()
    return n


def restore_seed_industries(session: Session) -> int:
    """
    seed에 정의된 업종을, 현재 미분류인 동일 corp에만 복구한다.
    DART corpCode sync가 예전에 미분류로 덮어쓴 경우를 교정.
    """
    with SEED_PATH.open(encoding="utf-8") as f:
        rows = json.load(f)
    restored = 0
    now = datetime.utcnow().isoformat(timespec="seconds")
    for row in rows:
        corp = str(row.get("corp_code") or "").strip()
        industry = _classified_industry(row.get("industry"))
        if not corp or not industry:
            continue
        company = session.get(Company, corp)
        if company is None or not is_unclassified(company.industry):
            continue
        company.industry = industry
        company.industry_source = "seed"
        company.industry_confidence = 1.0
        company.industry_updated_at = now
        session.add(company)
        restored += 1
    if restored:
        session.commit()
        logger.info("seed 업종 복구: %s건", restored)
    return restored


def load_seed_companies(session: Session) -> int:
    with SEED_PATH.open(encoding="utf-8") as f:
        rows = json.load(f)
    return upsert_companies(session, rows, industry_source="seed")


def sync_listed_companies_from_dart(session: Session) -> dict:
    """DART corpCode로 상장사 전체를 동기화한다. 이름/종목코드 중복은 최신만 유지."""
    rows = fetch_listed_companies_from_dart()
    kept, dropped = dedupe_listed_rows(rows)
    n = upsert_companies(session, kept)
    keep_ids = {str(r["corp_code"]).strip() for r in kept}
    pruned = prune_companies_not_in(session, keep_ids)
    restored = restore_seed_industries(session)
    logger.info(
        "Company Master sync: raw=%s kept=%s dropped=%s pruned_db=%s seed_restored=%s",
        len(rows),
        len(kept),
        len(dropped),
        pruned,
        restored,
    )
    return {
        "status": "ready",
        "source": "dart",
        "count": count_companies(session),
        "upserted": n,
        "raw": len(rows),
        "deduped": len(kept),
        "dropped_duplicates": len(dropped),
        "pruned": pruned,
        "seed_industry_restored": restored,
    }


def ensure_company_master(session: Session) -> dict:
    """
    Company Master 준비.
    - 비어 있으면 DART(상장사) 우선, 실패 시 seed
    - seed 수준(소수)만 있으면 DART로 업그레이드 시도
    - 기동 시 seed 업종(미분류로 덮인 경우) 복구
    """
    existing = count_companies(session)

    if existing == 0:
        try:
            result = sync_listed_companies_from_dart(session)
            restore_seed_industries(session)
            result["seed_industry_restored"] = True
            return result
        except DartCorpCodeError as exc:
            logger.warning("DART 로드 생략 → seed 사용: %s", exc)
            n = load_seed_companies(session)
            return {"status": "ready", "source": "seed", "count": n}

    if existing < SEED_THRESHOLD:
        try:
            result = sync_listed_companies_from_dart(session)
            restore_seed_industries(session)
            logger.info("Company Master seed→DART 업그레이드: %s", result)
            return result
        except DartCorpCodeError as exc:
            logger.warning("DART 업그레이드 실패, 기존 DB 유지: %s", exc)
            return {"status": "ready", "source": "db", "count": existing, "warning": str(exc)}

    restored = restore_seed_industries(session)
    return {
        "status": "ready",
        "source": "db",
        "count": existing,
        "seed_industry_restored": restored,
    }


def search_companies(session: Session, q: str, limit: int = 20) -> list[Company]:
    query = (q or "").strip()
    if not query:
        return []

    limit = max(1, min(limit, 50))
    fetch_limit = min(limit * 5, 100)

    if query.isdigit():
        # 종목코드만 매칭. corp_code 접두 매칭은 LF(00593032) 등이 005930에 섞이는 오탐 원인이었다.
        code = query.zfill(6)
        if len(query) >= 6:
            stmt = select(Company).where(Company.stock_code == code).limit(fetch_limit)
        else:
            stmt = (
                select(Company)
                .where(Company.stock_code.startswith(query))
                .limit(fetch_limit)
            )
        rows = list(session.exec(stmt).all())
    else:
        pattern = f"%{query}%"
        stmt = (
            select(Company)
            .where(col(Company.company_name).like(pattern))
            .limit(fetch_limit)
        )
        rows = list(session.exec(stmt).all())

    rows.sort(key=lambda c: _search_rank(c, query))
    # 방어: 동일 종목코드·동일 기업명이 결과에 중복되면 1건만
    return _unique_search_hits(rows)[:limit]


def _unique_search_hits(rows: list[Company]) -> list[Company]:
    seen_stock: set[str] = set()
    seen_name: set[str] = set()
    out: list[Company] = []
    for company in rows:
        stock = (company.stock_code or "").strip()
        name = (company.company_name or "").strip()
        if stock and stock in seen_stock:
            continue
        if name and name in seen_name:
            continue
        if stock:
            seen_stock.add(stock)
        if name:
            seen_name.add(name)
        out.append(company)
    return out


def _search_rank(company: Company, query: str) -> tuple:
    """
    낮을수록 우선.
    0: 종목코드/기업명 정확 일치
    1: 접두 일치 (같은 순위면 이름 짧은 쪽 우선)
    2: 부분 일치
    """
    name = (company.company_name or "").strip()
    stock = (company.stock_code or "").strip()

    if query.isdigit():
        code = query.zfill(6)
        if stock == code:
            return (0, 0, name)
        if stock.startswith(query):
            return (1, len(stock), name)
        return (2, len(name), name)

    if name == query:
        return (0, 0, name)
    if name.startswith(query):
        return (1, len(name), name)
    if name.lower() == query.lower():
        return (0, 0, name)
    if name.lower().startswith(query.lower()):
        return (1, len(name), name)
    return (2, len(name), name)


def get_company(session: Session, company_id: str) -> Company | None:
    return session.get(Company, company_id)
