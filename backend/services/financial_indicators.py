"""재무지표 계산 및 다년 추세 구성."""
from __future__ import annotations

from typing import Any

from services.financial_data import (
    period_kind,
    period_label_ko,
    period_sort_key,
    yoy_peer_period,
)


def _num(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numer: float | None, denom: float | None, *, as_percent: bool = True) -> float | None:
    if numer is None or denom is None or denom == 0:
        return None
    value = numer / denom
    return round(value * 100, 2) if as_percent else round(value, 4)


def _growth(current: float | None, previous: float | None) -> float | None:
    """성장률(%) = (현재 - 비교) / |비교| * 100. 비교값 0/없음이면 None."""
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def compute_period_indicators(metrics: dict[str, Any]) -> dict[str, Any]:
    """단일 기간 raw metrics → 핵심 지표."""
    revenue = _num(metrics, "revenue")
    operating_income = _num(metrics, "operating_income")
    net_income = _num(metrics, "net_income")
    ocf = _num(metrics, "operating_cash_flow")
    fcf = _num(metrics, "fcf")
    total_assets = _num(metrics, "total_assets")
    total_liabilities = _num(metrics, "total_liabilities")
    total_equity = _num(metrics, "total_equity")
    current_assets = _num(metrics, "current_assets")
    current_liabilities = _num(metrics, "current_liabilities")
    interest_expense = _num(metrics, "interest_expense")

    invested_capital = None
    if total_assets is not None and current_liabilities is not None:
        invested_capital = total_assets - current_liabilities

    return {
        "revenue": revenue,
        "operating_income": operating_income,
        "net_income": net_income,
        "operating_cash_flow": ocf,
        "fcf": fcf,
        "roe": _ratio(net_income, total_equity),
        "roic": _ratio(operating_income, invested_capital),
        "operating_margin": _ratio(operating_income, revenue),
        "debt_ratio": _ratio(total_liabilities, total_equity),
        "current_ratio": _ratio(current_assets, current_liabilities),
        "interest_coverage": _ratio(operating_income, interest_expense, as_percent=False),
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "interest_expense": interest_expense,
        "currency": metrics.get("currency", "KRW"),
        "unit": metrics.get("unit", "원"),
        "ratio_unit": "% (이자보상배율은 배수)",
    }


def _metric_comparison(
    metric: str,
    metric_ko: str,
    current_period: str,
    current_value: float | None,
    base_period: str | None,
    base_value: float | None,
) -> dict[str, Any]:
    rate = _growth(current_value, base_value)
    available = base_period is not None and base_value is not None and current_value is not None
    return {
        "metric": metric,
        "metric_ko": metric_ko,
        "current_period": current_period,
        "current_period_label": period_label_ko(current_period),
        "current_value": current_value,
        "comparison_period": base_period,
        "comparison_period_label": period_label_ko(base_period) if base_period else None,
        "comparison_value": base_value,
        "growth_rate": rate,
        "comparison_type": "전년 동기 대비" if available else None,
        "available": bool(available and rate is not None)
        or (available and base_value == 0 and current_value is not None),
        "unavailable_reason": None
        if (base_period and base_value is not None)
        else "동일 기간의 전년 데이터가 없어 전년 대비 성장률을 계산할 수 없습니다.",
    }


def build_yoy_comparisons(
    current: dict[str, Any],
    base: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """최신 기간 vs 전년 동기 성장률 묶음 (AI·rule 공용)."""
    cur_period = str(current.get("period") or "")
    base_period = str(base.get("period")) if base else None
    metrics = [
        ("revenue", "매출"),
        ("operating_income", "영업이익"),
        ("net_income", "순이익"),
        ("operating_cash_flow", "영업현금흐름"),
        ("fcf", "FCF"),
        ("operating_margin", "영업이익률"),
        ("roe", "ROE"),
        ("roic", "ROIC"),
        ("debt_ratio", "부채비율"),
        ("current_ratio", "유동비율"),
    ]
    out: list[dict[str, Any]] = []
    for key, label in metrics:
        out.append(
            _metric_comparison(
                key,
                label,
                cur_period,
                current.get(key),
                base_period,
                base.get(key) if base else None,
            )
        )
    return out


def group_series_by_kind(trend_desc: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """기간 유형별로만 묶은 시계열 (분기·반기·연간을 섞지 않음)."""
    grouped: dict[str, list[dict[str, Any]]] = {"FY": [], "Q1": [], "H1": [], "Q3": []}
    for point in trend_desc:
        kind = period_kind(str(point.get("period") or ""))
        if kind in grouped:
            grouped[kind].append(
                {
                    "period": point.get("period"),
                    "period_label": period_label_ko(str(point.get("period") or "")),
                    "revenue": point.get("revenue"),
                    "operating_income": point.get("operating_income"),
                    "operating_margin": point.get("operating_margin"),
                    "roe": point.get("roe"),
                    "operating_cash_flow": point.get("operating_cash_flow"),
                    "fcf": point.get("fcf"),
                    "revenue_growth_yoy": point.get("revenue_growth"),
                    "operating_income_growth_yoy": point.get("operating_income_growth"),
                    "growth_base_period": point.get("growth_base_period"),
                    "growth_comparison_type": point.get("growth_comparison_type"),
                }
            )
    return {k: v for k, v in grouped.items() if v}


def build_indicators_payload(period_items: list[dict[str, Any]]) -> dict[str, Any]:
    """
    financials 기간 목록을 받아 latest / trend / growth 를 구성한다.

    성장률은 연속 기간이 아니라 **전년 동기**(동일 Q1/H1/Q3/연간)만 비교한다.
    """
    if not period_items:
        return {
            "latest": None,
            "trend": [],
            "growth": None,
            "yoy_comparisons": [],
            "series_by_kind": {},
        }

    chronological = sorted(
        period_items, key=lambda x: period_sort_key(str(x.get("period") or ""))
    )

    # 기간별 지표 맵 (전년 동기 조회용)
    computed: list[dict[str, Any]] = []
    by_period: dict[str, dict[str, Any]] = {}
    for item in chronological:
        period = str(item.get("period") or "")
        indicators = compute_period_indicators(item.get("metrics") or {})
        point = {
            "period": period,
            "source": item.get("source"),
            "fs_div": item.get("fs_div"),
            "reprt_code": item.get("reprt_code"),
            **indicators,
        }
        computed.append(point)
        by_period[period] = point

    trend: list[dict[str, Any]] = []
    for point in computed:
        period = point["period"]
        peer_label = yoy_peer_period(period)
        peer = by_period.get(peer_label) if peer_label else None
        revenue_growth = _growth(point.get("revenue"), peer.get("revenue") if peer else None)
        op_growth = _growth(
            point.get("operating_income"),
            peer.get("operating_income") if peer else None,
        )
        enriched = {
            **point,
            "revenue_growth": revenue_growth,
            "operating_income_growth": op_growth,
            "growth_base_period": peer_label if peer else None,
            "growth_comparison_type": "전년 동기 대비" if peer else None,
            "growth_available": peer is not None,
        }
        if peer is None:
            enriched["growth_unavailable_reason"] = (
                "동일 기간의 전년 데이터가 없어 전년 대비 성장률을 계산할 수 없습니다."
            )
        trend.append(enriched)

    latest = trend[-1]
    base_period = latest.get("growth_base_period")
    growth = {
        "period": latest["period"],
        "period_label": period_label_ko(str(latest["period"])),
        "revenue_growth": latest.get("revenue_growth"),
        "operating_income_growth": latest.get("operating_income_growth"),
        "base_period": base_period,
        "base_period_label": period_label_ko(base_period) if base_period else None,
        "comparison_type": latest.get("growth_comparison_type"),
        "available": bool(latest.get("growth_available")),
        "unavailable_reason": latest.get("growth_unavailable_reason"),
    }

    trend_desc = list(reversed(trend))
    base_point = by_period.get(base_period) if base_period else None
    yoy_comparisons = build_yoy_comparisons(latest, base_point)

    return {
        "latest": latest,
        "trend": trend_desc,
        "growth": growth,
        "yoy_comparisons": yoy_comparisons,
        "series_by_kind": group_series_by_kind(trend_desc),
        "periods": len(trend_desc),
        "comparison_rules": {
            "method": "전년 동기 대비",
            "rules": [
                "분기(Q1/Q3)는 동일 분기끼리만 비교",
                "반기(H1)는 반기끼리만 비교",
                "연간은 연간끼리만 비교",
                "분기·반기·연간을 섞어 성장률을 계산하지 않음",
                "전년 동기 데이터가 없으면 성장률을 계산하지 않음",
            ],
        },
    }
