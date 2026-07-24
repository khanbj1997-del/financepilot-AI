"""업종 특성 정적 참고 데이터 로드·조회·AI 프롬프트 힌트."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from models.company import Company
from services.industry_taxonomy import profile_key_for

PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "industry_profiles.json"


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with PROFILE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def list_industries() -> list[str]:
    raw = _load_raw()
    return sorted(k for k in raw.keys() if not k.startswith("_") and k != "default")


def get_profile(industry: str | None) -> dict[str, Any]:
    raw = _load_raw()
    key = profile_key_for(industry)
    if key and key in raw:
        profile = dict(raw[key])
        profile["matched"] = key != "default"
        profile["profile_key"] = key
        profile["requested_industry"] = industry
        return profile
    profile = dict(raw.get("default") or {})
    profile["matched"] = False
    profile["profile_key"] = "default"
    profile["requested_industry"] = industry
    return profile


def get_profile_for_company(company: Company) -> dict[str, Any]:
    return get_profile(company.industry)


def build_analysis_context(
    company: Company,
    indicators_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    AI 분석(A5)에 넣을 '일반 기준 + 업종 + 추세' 컨텍스트.
    프롬프트 조립용 구조화 데이터 + 텍스트 힌트.
    """
    profile = get_profile_for_company(company)
    latest = (indicators_payload or {}).get("latest") or {}
    growth = (indicators_payload or {}).get("growth") or {}
    trend = (indicators_payload or {}).get("trend") or []

    prompt_hints = {
        "framework": [
            "1) 일반 재무 기준",
            "2) 해당 업종 특성",
            "3) 과거 3~5년 추세",
            "위 세 가지를 함께 반영해 해석한다.",
        ],
        "must_not": [
            "존재하지 않는 수치나 사실을 생성하지 말 것",
            "투자 권유(매수/매도)를 하지 말 것",
            "부채비율·유동비율 등 단일 지표로 위험/안전을 단정하지 말 것",
        ],
        "industry_rules": profile.get("analysis_rules") or [],
        "metric_hints": profile.get("metric_hints") or {},
    }

    summary_lines = [
        f"기업: {company.company_name} (company_id={company.company_id})",
        f"업종: {company.industry or '미분류'} (profile={profile.get('profile_key')})",
        f"자본집약도: {profile.get('capital_intensity')}",
        f"수익구조: {profile.get('revenue_structure')}",
        f"유동성 참고: {profile.get('liquidity_note')}",
        f"수익성 참고: {profile.get('profitability_note')}",
    ]
    if latest:
        summary_lines.append(
            "최신지표: "
            f"기간={latest.get('period')}, "
            f"ROE={latest.get('roe')}, "
            f"영업이익률={latest.get('operating_margin')}, "
            f"부채비율={latest.get('debt_ratio')}, "
            f"유동비율={latest.get('current_ratio')}"
        )
    if growth:
        summary_lines.append(
            f"성장률: 매출={growth.get('revenue_growth')}, "
            f"영업이익={growth.get('operating_income_growth')} "
            f"(기준연도={growth.get('base_period')})"
        )

    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "industry": company.industry,
        "profile": profile,
        "indicators_latest": latest or None,
        "indicators_growth": growth or None,
        "trend_periods": [t.get("period") for t in trend],
        "prompt_hints": prompt_hints,
        "prompt_text": "\n".join(summary_lines),
    }
