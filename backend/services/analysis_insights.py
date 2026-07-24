"""AI·rule 분석용 지표 관계·갭·유동성 해석 힌트 (백엔드 사전 계산)."""
from __future__ import annotations

from typing import Any


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _dir(value: float | None) -> str | None:
    if value is None:
        return None
    if value > 0.5:
        return "증가"
    if value < -0.5:
        return "감소"
    return "횡보"


def _yoy_lookup(yoy_comparisons: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    for item in yoy_comparisons:
        if item.get("metric") == metric:
            return item
    return None


def assess_current_ratio(
    current_ratio: float | None,
    *,
    capital_intensity: str | None = None,
) -> dict[str, Any]:
    """유동비율 수준 분류. 극단적으로 높아도 재투자 부족을 단정하지 않는다."""
    if current_ratio is None:
        return {
            "level": "unknown",
            "value": None,
            "is_extreme_high": False,
            "hints": ["유동비율 데이터가 없어 유동성 해석이 제한적입니다."],
            "do_not_conclude": [
                "유동비율이 높다 = 재투자가 부족하다 라고 단정하지 말 것",
            ],
        }

    intensity = (capital_intensity or "").strip().lower()
    # 자본집약 업종은 설비·재고 특성상 유동성 기준이 다를 수 있음
    extreme_threshold = 350.0 if "고" in (capital_intensity or "") or "high" in intensity else 300.0
    elevated_threshold = 200.0

    if current_ratio < 80:
        level = "low"
        is_extreme = False
        hints = [
            "단기 지급능력·유동성 여유가 제한적일 수 있어 영업현금흐름과 함께 볼 필요가 있습니다.",
        ]
    elif current_ratio < elevated_threshold:
        level = "adequate"
        is_extreme = False
        hints = [
            "단기 지급능력 측면에서 일반적으로 무리 없는 구간에 가깝습니다.",
            "업종·사업 단계에 따라 적정 수준이 달라지므로 절대 기준으로 단정하지 않습니다.",
        ]
    elif current_ratio < extreme_threshold:
        level = "elevated"
        is_extreme = False
        hints = [
            "단기 지급능력은 충분한 편일 수 있습니다.",
            "업종 특성과 성장 단계에 비해 유동성이 높은 편이면 자본 활용·재투자 여부를 확인할 여지가 있습니다.",
            "높은 유동성이 곧바로 높은 기업가치나 성장을 의미하지는 않습니다.",
        ]
    else:
        level = "extreme_high"
        is_extreme = True
        hints = [
            "단기 지급능력 측면에서는 긍정적일 수 있습니다.",
            "다만 유동자산이 과도하게 축적되었을 가능성도 있어, 설비투자·연구개발·사업 확장 등 자본 배분이 충분한지 확인할 필요가 있습니다.",
            "재투자 부족을 사실로 단정하지 말고, 확인이 필요한 관점으로만 제시합니다.",
            "자본집약도와 업종 유동성 특성을 함께 고려합니다.",
        ]

    return {
        "level": level,
        "value": current_ratio,
        "is_extreme_high": is_extreme,
        "elevated_or_extreme": level in {"elevated", "extreme_high"},
        "capital_intensity": capital_intensity,
        "hints": hints,
        "do_not_conclude": [
            "유동비율이 높다 = 재투자가 부족하다 라고 단정하지 말 것",
            "투자·R&D 데이터가 없으면 자본 배분 부족을 사실처럼 쓰지 말 것",
        ],
    }


def build_same_kind_sequential(
    series_by_kind: dict[str, list[dict[str, Any]]],
    latest_period: str,
    period_kind_fn,
    period_label_fn,
) -> dict[str, Any]:
    """동일 기간 유형의 직전 구간 대비 변화 (전년 동기와 별개)."""
    kind = period_kind_fn(latest_period)
    series = series_by_kind.get(kind) or []
    if len(series) < 2:
        return {
            "available": False,
            "period_kind": kind,
            "reason": "동일 기간 유형의 직전 구간 데이터가 부족합니다.",
        }

    current = series[0]
    prior = series[1]
    metrics = ("revenue", "operating_income", "operating_margin", "operating_cash_flow", "fcf")
    changes: dict[str, Any] = {}
    for key in metrics:
        rate = _growth(_f(current.get(key)), _f(prior.get(key)))
        changes[key] = {
            "current": _f(current.get(key)),
            "prior": _f(prior.get(key)),
            "change_pct": rate,
            "direction": _dir(rate),
        }

    return {
        "available": True,
        "period_kind": kind,
        "comparison_type": "동일 유형 직전 구간 대비",
        "current_period": current.get("period"),
        "current_period_label": period_label_fn(str(current.get("period") or "")),
        "prior_period": prior.get("period"),
        "prior_period_label": period_label_fn(str(prior.get("period") or "")),
        "changes": changes,
        "note": "전년 동기 대비와 다른 비교입니다. 혼용하지 마세요.",
    }


def build_metric_relations(
    latest: dict[str, Any],
    growth: dict[str, Any],
    yoy_comparisons: list[dict[str, Any]],
    *,
    capital_intensity: str | None = None,
) -> dict[str, Any]:
    """지표 간 관계 요약 — AI는 이를 우선 해석하고 임의 재계산하지 않는다."""
    rev = _yoy_lookup(yoy_comparisons, "revenue")
    op = _yoy_lookup(yoy_comparisons, "operating_income")
    margin = _yoy_lookup(yoy_comparisons, "operating_margin")
    ocf_yoy = _yoy_lookup(yoy_comparisons, "operating_cash_flow")
    fcf_yoy = _yoy_lookup(yoy_comparisons, "fcf")

    rev_g = _f((rev or {}).get("growth_rate"))
    if rev_g is None:
        rev_g = _f(growth.get("revenue_growth"))
    op_g = _f((op or {}).get("growth_rate"))
    if op_g is None:
        op_g = _f(growth.get("operating_income_growth"))
    margin_g = _f((margin or {}).get("growth_rate"))
    ocf_g = _f((ocf_yoy or {}).get("growth_rate"))
    fcf_g = _f((fcf_yoy or {}).get("growth_rate"))

    op_income = _f(latest.get("operating_income"))
    ocf = _f(latest.get("operating_cash_flow"))
    fcf = _f(latest.get("fcf"))
    op_margin = _f(latest.get("operating_margin"))
    debt = _f(latest.get("debt_ratio"))
    current = _f(latest.get("current_ratio"))
    prior_margin = _f((margin or {}).get("comparison_value"))

    aligned_rev_op = None
    if rev_g is not None and op_g is not None:
        aligned_rev_op = (rev_g > 0 and op_g > 0) or (rev_g < 0 and op_g < 0) or (
            abs(rev_g) <= 0.5 and abs(op_g) <= 0.5
        )

    op_outpaces = None
    if rev_g is not None and op_g is not None:
        op_outpaces = op_g > rev_g

    margin_improved = None
    if op_margin is not None and prior_margin is not None:
        margin_improved = op_margin > prior_margin

    same_sign_op_ocf = None
    if op_income is not None and ocf is not None:
        same_sign_op_ocf = (op_income >= 0 and ocf >= 0) or (op_income < 0 and ocf < 0)

    return {
        "revenue_vs_operating_income": {
            "revenue_growth_yoy": rev_g,
            "operating_income_growth_yoy": op_g,
            "directions_aligned": aligned_rev_op,
            "operating_income_outpaces_revenue": op_outpaces,
            "interpretation": (
                "매출·영업이익이 전년 동기 기준 같은 방향"
                if aligned_rev_op is True
                else "매출·영업이익 방향이 전년 동기 기준 불일치"
                if aligned_rev_op is False
                else "매출·영업이익 동행 여부를 판단할 전년 동기 성장률이 부족"
            ),
        },
        "operating_income_vs_margin": {
            "operating_income_growth_yoy": op_g,
            "operating_margin_current": op_margin,
            "operating_margin_yoy_change": margin_g,
            "margin_improved_vs_yoy_peer": margin_improved,
            "interpretation": (
                "이익 증가와 마진 개선이 함께 나타나는지 확인 필요"
                if op_g is not None
                else "영업이익 성장률 데이터 부족"
            ),
        },
        "operating_income_vs_ocf": {
            "operating_income": op_income,
            "operating_cash_flow": ocf,
            "same_sign": same_sign_op_ocf,
            "operating_income_growth_yoy": op_g,
            "ocf_growth_yoy": ocf_g,
            "interpretation": (
                "회계상 이익과 영업현금 부호가 일치"
                if same_sign_op_ocf is True
                else "이익과 영업현금 방향이 달라 이익의 질 확인 필요"
                if same_sign_op_ocf is False
                else "영업이익 또는 영업현금흐름 데이터 부족"
            ),
        },
        "ocf_vs_fcf": {
            "operating_cash_flow": ocf,
            "fcf": fcf,
            "ocf_growth_yoy": ocf_g,
            "fcf_growth_yoy": fcf_g,
            "both_positive": (ocf is not None and fcf is not None and ocf > 0 and fcf > 0),
            "ocf_positive_fcf_negative": (ocf is not None and fcf is not None and ocf > 0 and fcf < 0),
            "interpretation": (
                "영업CF는 양수이나 FCF가 음수 — 투자 부담 가능성(원인은 데이터 없으면 추측 금지)"
                if (ocf is not None and fcf is not None and ocf > 0 and fcf < 0)
                else "영업CF·FCF가 함께 양수"
                if (ocf is not None and fcf is not None and ocf > 0 and fcf > 0)
                else "현금흐름 해석을 위한 데이터 확인 필요"
            ),
        },
        "current_ratio_view": assess_current_ratio(current, capital_intensity=capital_intensity),
        "debt_vs_profitability": {
            "debt_ratio": debt,
            "operating_margin": op_margin,
            "roe": _f(latest.get("roe")),
            "low_debt": debt is not None and debt <= 50,
            "high_debt": debt is not None and debt >= 150,
            "interpretation": (
                "낮은 부채비율은 안정성에 도움이 될 수 있으나, 업종에 따라 성장 투자용 레버리지 활용도와 함께 봐야 함"
                if debt is not None and debt <= 50
                else "높은 부채비율은 현금흐름 감당 능력과 함께 봐야 함"
                if debt is not None and debt >= 150
                else "부채비율과 수익성을 업종 맥락에서 함께 해석"
            ),
        },
        "high_growth_caution": {
            "very_high_op_growth": op_g is not None and op_g >= 100,
            "very_high_rev_growth": rev_g is not None and rev_g >= 50,
            "hints": [
                "성장률이 매우 높으면 기저효과·일회성 가능성을 열어두되, 데이터 없이 일회성이라고 단정하지 말 것",
                "매출·이익·마진·영업현금의 동행과 다음 공시 유지 여부를 확인 포인트로 제시",
            ],
        },
    }


def build_data_gaps(latest: dict[str, Any], growth: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    checks = [
        ("revenue", "매출"),
        ("operating_income", "영업이익"),
        ("operating_margin", "영업이익률"),
        ("operating_cash_flow", "영업현금흐름"),
        ("fcf", "FCF"),
        ("debt_ratio", "부채비율"),
        ("current_ratio", "유동비율"),
        ("roe", "ROE"),
    ]
    for key, label in checks:
        if latest.get(key) is None:
            gaps.append(f"{label} 원본 수치 없음")
    if growth.get("revenue_growth") is None:
        gaps.append("전년 동기 매출 성장률 계산 불가(동일 기간 전년 데이터 부족 가능)")
    if growth.get("operating_income_growth") is None:
        gaps.append("전년 동기 영업이익 성장률 계산 불가")
    # R&D / capex not in MVP metrics
    gaps.append("연구개발비·설비투자 상세는 MVP 제공 범위에 없어 재투자 규모를 단정할 수 없음")
    return gaps


def infer_growth_stage_hint(
    latest: dict[str, Any],
    growth: dict[str, Any],
    metric_relations: dict[str, Any],
) -> dict[str, Any]:
    """재무 수치만으로 성장 단계 '힌트'를 만든다. 단정 금지."""
    rev_g = _f(growth.get("revenue_growth"))
    op_g = _f(growth.get("operating_income_growth"))
    revenue = _f(latest.get("revenue"))
    high_g = metric_relations.get("high_growth_caution") or {}
    op_ocf = metric_relations.get("operating_income_vs_ocf") or {}

    if high_g.get("very_high_rev_growth") or high_g.get("very_high_op_growth"):
        stage = "고성장·급반등 구간 가능성"
        note = (
            "전년 동기 대비 성장률이 매우 높아 확장·업황 반등 구간일 수 있으나, "
            "한 기간만으로 성장 단계를 확정하지 않습니다."
        )
    elif rev_g is not None and op_g is not None and rev_g < 0 and op_g < 0:
        stage = "수축·조정 구간 가능성"
        note = "외형과 이익이 함께 줄어 수요·가격 조정 구간일 수 있습니다."
    elif rev_g is not None and abs(rev_g) < 5 and op_g is not None and abs(op_g) < 10:
        stage = "안정·성숙 구간 가능성"
        note = "성장률 변동이 크지 않아 안정 구간에 가깝게 보일 수 있습니다."
    elif rev_g is not None and rev_g > 0 and op_g is not None and op_g > 0:
        stage = "성장 구간 가능성"
        note = "매출·이익이 함께 늘어 성장 구간에 가깝습니다."
    else:
        stage = "판단 자료 제한"
        note = "성장 단계를 특정할 전년 동기 비교가 부족하거나 방향이 혼재합니다."

    return {
        "stage_hint": stage,
        "note": note,
        "revenue_scale": revenue,
        "cash_supports_earnings": op_ocf.get("same_sign") is True,
        "do_not_treat_as_fact": True,
    }


def build_industry_analysis_context(
    profile: dict[str, Any],
    *,
    company_industry: str | None,
    growth_stage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """업종 프로필을 AI가 바로 쓰도록 구조화. '업종을 고려하라' 수준으로 끝내지 않게 함."""
    industry = company_industry or profile.get("industry") or "일반"
    capital = profile.get("capital_intensity") or "중간"
    return {
        "industry_name": industry,
        "profile_key": profile.get("profile_key") or "default",
        "matched": bool(profile.get("matched")),
        "capital_intensity": capital,
        "revenue_structure": profile.get("revenue_structure"),
        "liquidity_note": profile.get("liquidity_note"),
        "profitability_note": profile.get("profitability_note"),
        "analysis_rules": profile.get("analysis_rules") or [],
        "metric_hints": profile.get("metric_hints") or {},
        "growth_stage_hint": growth_stage,
        "how_to_use": [
            "업종명·자본집약도·liquidity_note·profitability_note를 실제 문장에 반영할 것",
            "'업종 특성을 고려할 필요가 있습니다'라고만 쓰지 말 것",
            "프로필에 없는 산업 사실을 지어내지 말 것",
        ],
    }


def build_external_evidence_slot() -> dict[str, Any]:
    """향후 웹검색 연동용 슬롯. 현재 MVP에는 검색이 연결되어 있지 않음."""
    return {
        "web_search_enabled": False,
        "status": "not_connected",
        "findings": [],
        "instruction": (
            "외부 검색·공시 원문 검색이 연결되어 있지 않습니다. "
            "실적 개선 원인(수주·신제품·일회성 등)을 추측하지 말고 "
            "재무 스냅샷과 업종 프로필만으로 판단 가능한 결론을 먼저 제시하십시오."
        ),
        "future_hook": (
            "연동 시 findings에 {source, summary, relevance}를 넣고 "
            "재무 수치와 연결 가능한 항목만 종합 판단·성장성·위험요인에 반영한다."
        ),
    }


def build_analysis_insights(
    indicators: dict[str, Any],
    *,
    capital_intensity: str | None = None,
    period_kind_fn=None,
    period_label_fn=None,
    profile: dict[str, Any] | None = None,
    company_industry: str | None = None,
) -> dict[str, Any]:
    latest = indicators.get("latest") or {}
    growth = indicators.get("growth") or {}
    yoy = indicators.get("yoy_comparisons") or []
    series = indicators.get("series_by_kind") or {}
    period = str(latest.get("period") or "")
    profile = profile or {}

    sequential = {"available": False, "reason": "기간 헬퍼 미제공"}
    if period_kind_fn and period_label_fn and period:
        sequential = build_same_kind_sequential(series, period, period_kind_fn, period_label_fn)

    relations = build_metric_relations(
        latest, growth, yoy, capital_intensity=capital_intensity or profile.get("capital_intensity")
    )
    growth_stage = infer_growth_stage_hint(latest, growth, relations)

    return {
        "metric_relations": relations,
        "same_kind_sequential": sequential,
        "data_gaps": build_data_gaps(latest, growth),
        "growth_stage_hint": growth_stage,
        "industry_analysis_context": build_industry_analysis_context(
            profile, company_industry=company_industry, growth_stage=growth_stage
        ),
        "external_evidence": build_external_evidence_slot(),
        "analysis_flow": [
            "원본 재무 수치",
            "기간별·전년 동기 변화",
            "지표 간 관계",
            "업종·성장단계 맥락(프로필 범위)",
            "판단 가능한 결론 제시",
            "데이터로 확정 불가한 항목만 잔여 확인 포인트로 구분",
            "향후 검증 질문",
        ],
        "conclusion_first_rules": [
            "현재 데이터로 판단 가능한 것은 반드시 결론을 내린다",
            "'확인해야 합니다'만으로 분석을 끝내지 않는다",
            "외부 검색이 없으면 원인을 추측하지 않는다",
        ],
    }
