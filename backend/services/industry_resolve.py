"""기업 업종 해석: DART 원본 > seed > Groq 추정 > 미분류."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session

from models.company import Company
from services.dart_company_overview import DartCompanyInfoError, fetch_company_overview
from services.industry_groq import estimate_industry_with_groq
from services.industry_taxonomy import (
    is_unclassified,
    map_induty_code,
    normalize_industry,
    profile_key_for,
)

logger = logging.getLogger(__name__)


def _set_industry(
    company: Company,
    *,
    industry: str,
    source: str,
    confidence: float | None = None,
) -> None:
    company.industry = industry
    company.industry_source = source
    company.industry_confidence = confidence
    company.industry_updated_at = datetime.utcnow().isoformat(timespec="seconds")


def _mark_unresolved(company: Company) -> None:
    company.industry = company.industry if not is_unclassified(company.industry) else "미분류"
    if is_unclassified(company.industry):
        company.industry = "미분류"
    company.industry_source = "unresolved"
    company.industry_confidence = 0.0
    company.industry_updated_at = datetime.utcnow().isoformat(timespec="seconds")


def ensure_company_industry(
    session: Session,
    company: Company,
    *,
    allow_groq: bool = True,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    업종이 없거나 미분류일 때만 보강한다.
    정상 업종이 있으면 Groq/DART를 호출하지 않는다 (force_refresh 제외).

    우선순위: 기존 정상값 → DART company.json 업종코드 매핑 → Groq → 미분류
    이미 해석을 시도해 unresolved로 표시된 경우(강제 제외) API를 재호출하지 않는다.
    """
    if not force_refresh and not is_unclassified(company.industry):
        return {
            "industry": company.industry,
            "industry_source": company.industry_source or "unknown",
            "industry_confidence": company.industry_confidence,
            "resolved": False,
            "action": "keep_existing",
            "profile_key": profile_key_for(company.industry),
        }

    if (
        not force_refresh
        and is_unclassified(company.industry)
        and company.industry_source == "unresolved"
        and company.industry_updated_at
    ):
        return {
            "industry": company.industry or "미분류",
            "industry_source": "unresolved",
            "industry_confidence": company.industry_confidence,
            "resolved": False,
            "action": "skip_cached_unresolved",
        }

    overview: dict[str, Any] | None = None
    try:
        overview = fetch_company_overview(company.corp_code or company.company_id)
    except DartCompanyInfoError as exc:
        logger.info("기업개황 생략(%s): %s", company.company_id, exc)

    if overview:
        mapped = map_induty_code(str(overview.get("induty_code") or ""))
        mapped = normalize_industry(mapped)
        if mapped:
            _set_industry(company, industry=mapped, source="dart", confidence=1.0)
            session.add(company)
            session.commit()
            session.refresh(company)
            return {
                "industry": company.industry,
                "industry_source": "dart",
                "industry_confidence": 1.0,
                "induty_code": overview.get("induty_code"),
                "resolved": True,
                "action": "dart_mapped",
                "profile_key": profile_key_for(company.industry),
            }

    if allow_groq:
        estimated = estimate_industry_with_groq(company, overview)
        if estimated:
            _set_industry(
                company,
                industry=estimated["industry"],
                source="groq",
                confidence=estimated.get("confidence"),
            )
            session.add(company)
            session.commit()
            session.refresh(company)
            return {
                "industry": company.industry,
                "industry_source": "groq",
                "industry_confidence": company.industry_confidence,
                "reason": estimated.get("reason"),
                "resolved": True,
                "action": "groq_estimated",
                "profile_key": profile_key_for(company.industry),
            }

    _mark_unresolved(company)
    session.add(company)
    session.commit()
    session.refresh(company)

    return {
        "industry": company.industry or "미분류",
        "industry_source": company.industry_source or "unresolved",
        "industry_confidence": company.industry_confidence,
        "resolved": False,
        "action": "unclassified",
    }
