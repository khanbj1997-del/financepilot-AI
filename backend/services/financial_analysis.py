"""종합 재무 분석: rule / Groq(+Gemini·OpenAI 코드 유지) + 캐시."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from models.analysis_cache import AnalysisCache
from models.company import Company
from services.analysis_insights import build_analysis_insights
from services.financial_data import get_or_load_financials
from services.financial_indicators import build_indicators_payload
from services.gemini_client import GeminiClient, GeminiError
from services.groq_client import GroqClient, GroqError
from services.industry_profile import build_analysis_context
from services.openai_client import OpenAIClient, OpenAIError
from services.text_sanitize import (
    overall_lacks_conclusion,
    sanitize_korean_output,
)
from utils.number_format import (
    build_display_metrics,
    format_financial_amount,
    format_percent,
    rewrite_raw_numbers_in_text,
)

logger = logging.getLogger(__name__)

# 캐시 무효화용. 표시 포맷·스냅샷 display 필드 반영.
ANALYSIS_SCHEMA_VERSION = "v7"

REQUIRED_KEYS = (
    "overall_judgment",
    "key_variable",
    "financial_soundness",
    "profitability",
    "growth",
    "earnings_quality",
    "strengths",
    "risks",
    "key_questions",
    "data_to_watch",
)

_INFO_HINTS = (
    "ANALYSIS_PROVIDER=rule",
    "ANALYSIS_PROVIDER=groq",
    "ANALYSIS_PROVIDER=gemini",
    "seed 재무 데이터를 사용",
    "DART_API_KEY 미설정",
)


def _split_status_text(text: str | None) -> tuple[str | None, str | None]:
    """안내(notice)와 실패/경고(message)를 분리한다."""
    if not text:
        return None, None
    parts = [p.strip() for p in text.split("|") if p.strip()]
    notices: list[str] = []
    warnings: list[str] = []
    for part in parts:
        if any(h in part for h in _INFO_HINTS):
            notices.append(part)
        else:
            warnings.append(part)
    notice = " | ".join(notices) if notices else None
    message = " | ".join(warnings) if warnings else None
    return notice, message


def _fmt_pct(value: Any) -> str:
    return format_percent(value, empty="데이터 없음")


def _fmt_num(value: Any) -> str:
    return format_financial_amount(value, empty="데이터 없음")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cache_key(company_id: str, snapshot: dict[str, Any]) -> str:
    raw = json.dumps(
        {"company_id": company_id, "schema": ANALYSIS_SCHEMA_VERSION, **snapshot},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _as_str_list(value: Any, *, limit: int | None = None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        text = str(value).strip()
        items = [text] if text else []
    if limit is not None:
        items = items[:limit]
    return items


def _as_key_questions(value: Any, *, limit: int = 3) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, dict):
            q = str(item.get("question") or "").strip()
            why = str(
                item.get("why")
                or item.get("evidence")
                or item.get("reason")
                or ""
            ).strip()
            if q:
                why = _sanitize_question_why(q, why)
                out.append({"question": q, "why": why})
        else:
            text = str(item).strip()
            if text:
                out.append(
                    {
                        "question": text,
                        "why": "제공된 재무 지표상 해당 항목의 추세·관계가 해석의 분기점이 됩니다.",
                    }
                )
        if len(out) >= limit:
            break
    return out


def _sanitize_question_why(question: str, why: str) -> str:
    """질문 반복·공허한 '전략 필요' 문구를 걸러 최소 품질을 확보한다."""
    q = (question or "").strip()
    w = (why or "").strip()
    if not w:
        return (
            "제공된 스냅샷의 해당 지표 수준·직전 대비 변화가 "
            "다음 공시에서 확인해야 할 핵심 분기점이기 때문입니다."
        )

    weak_phrases = (
        "전략이 필요",
        "어떻게 할 것",
        "어떻게 극복",
        "어떻게 관리",
        "어떻게 유지",
        "중요한 지표이기 때문",
        "중요한 지표이므로",
        "평가하는 중요한",
        "우려가 있을 수 있기 때문",
    )
    # 질문과 why의 단어 겹침이 과도하면 반복으로 간주
    q_tokens = {t for t in q.replace("?", " ").split() if len(t) >= 2}
    w_tokens = {t for t in w.replace("?", " ").split() if len(t) >= 2}
    overlap = len(q_tokens & w_tokens) / max(len(q_tokens), 1)

    if any(p in w for p in weak_phrases) or overlap >= 0.55:
        return (
            "제공된 재무 스냅샷에서 관련 지표의 현재 수준과 직전 대비 변화가 "
            "해석을 가르는 지점이므로, 다음 공시 수치로 지속·반등·악화 여부를 확인해야 합니다."
        )
    return w


def _scrub_non_korean_phrases(text: str) -> str:
    """중국어·한자·가나 등 부자연 표현을 한국어로 정리."""
    return sanitize_korean_output(text)


def _normalize_result(data: dict[str, Any], data_as_of: str | None) -> dict[str, Any]:
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(f"분석 결과 필드 누락: {missing}")

    def scrub_str(value: Any) -> str:
        text = _scrub_non_korean_phrases(str(value).strip())
        raw_for_rewrite = None
        if isinstance(data.get("_snapshot"), dict):
            raw_for_rewrite = (data["_snapshot"].get("raw_metrics")
                              or data["_snapshot"].get("latest_metrics"))
        # growth 수치도 치환 후보에 합침
        if isinstance(data.get("_snapshot"), dict):
            growth = data["_snapshot"].get("growth") or data["_snapshot"].get("growth_yoy") or {}
            merged = dict(raw_for_rewrite or {})
            for k in ("revenue_growth", "operating_income_growth"):
                if growth.get(k) is not None:
                    merged[k] = growth.get(k)
            raw_for_rewrite = merged
        return rewrite_raw_numbers_in_text(text, raw_for_rewrite)

    strengths = [scrub_str(x) for x in _as_str_list(data.get("strengths"), limit=3)]
    risks = [scrub_str(x) for x in _as_str_list(data.get("risks"), limit=3)]
    watch = [scrub_str(x) for x in _as_str_list(data.get("data_to_watch"), limit=5)]
    questions = []
    for q in _as_key_questions(data.get("key_questions"), limit=3):
        questions.append(
            {
                "question": scrub_str(q["question"]),
                "why": scrub_str(q["why"]),
            }
        )

    if not risks:
        risks = [
            "현재 확인 가능한 재무 데이터에서는 뚜렷한 재무 건전성 위험요인이 제한적입니다."
        ]

    overall = scrub_str(data["overall_judgment"])
    key_variable = scrub_str(data.get("key_variable") or "핵심 지표 동행 여부")
    snapshot = data.get("_snapshot") if isinstance(data.get("_snapshot"), dict) else None

    # 수치 나열형·'확인 필요'만으로 끝나는 종합 판단은 결론형으로 재작성
    if overall_lacks_conclusion(overall):
        overall = _synthesize_overall_judgment(
            company_name=str(data.get("_company_name") or ""),
            key_variable=key_variable,
            snapshot=snapshot,
            fallback=overall,
        )
        overall = scrub_str(overall)

    return {
        "overall_judgment": overall,
        "key_variable": key_variable,
        "financial_soundness": scrub_str(data["financial_soundness"]),
        "profitability": scrub_str(data["profitability"]),
        "growth": scrub_str(data["growth"]),
        "earnings_quality": scrub_str(data["earnings_quality"]),
        "strengths": strengths,
        "risks": risks[:3],
        "key_questions": questions,
        "data_to_watch": watch,
        "data_as_of": data_as_of or data.get("data_as_of"),
        "disclaimer": scrub_str(
            data.get("disclaimer")
            or (
                "본 분석은 제공된 재무 수치에 근거한 참고용 해석이며 투자 권유가 아닙니다. "
                "없는 사실은 생성하지 않으며, 매수·매도 의견을 제시하지 않습니다."
            )
        ),
    }


def _synthesize_overall_judgment(
    *,
    company_name: str,
    key_variable: str,
    snapshot: dict[str, Any] | None,
    fallback: str,
) -> str:
    """확보된 데이터로 먼저 결론을 내리고, 확정 불가 항목만 잔여 포인트로 남긴다."""
    name = company_name or "해당 기업"
    relations = (snapshot or {}).get("metric_relations") or {}
    rev_op = relations.get("revenue_vs_operating_income") or {}
    op_ocf = relations.get("operating_income_vs_ocf") or {}
    high_g = relations.get("high_growth_caution") or {}
    industry_ctx = (snapshot or {}).get("industry_analysis_context") or {}
    rev_g = _as_float(rev_op.get("revenue_growth_yoy"))
    op_g = _as_float(rev_op.get("operating_income_growth_yoy"))
    same_cash = op_ocf.get("same_sign")
    industry = industry_ctx.get("industry_name")

    parts: list[str] = []
    if rev_g is not None and op_g is not None and rev_g > 0 and op_g > 0:
        if same_cash is True:
            parts.append(
                f"{name}의 최근 실적 개선은 매출 증가와 영업이익 증가가 동시에 나타나고 "
                "영업현금흐름도 같은 방향으로 보여, "
                "단순한 회계상 이익 증가보다 현금 창출력 개선이 동반된 것으로 판단됩니다."
            )
        elif same_cash is False:
            parts.append(
                f"{name}은 전년 동기 기준 매출·영업이익이 함께 늘었지만 "
                "영업이익과 영업현금흐름의 방향이 달라, "
                "외형·이익 개선이 현금 창출로 충분히 이어졌다고 보기는 어렵습니다."
            )
        else:
            parts.append(
                f"{name}의 최근 실적은 전년 동기 대비 매출과 영업이익이 함께 늘어 "
                "실적 방향은 긍정적으로 판단됩니다."
            )
        if high_g.get("very_high_op_growth") or high_g.get("very_high_rev_growth"):
            parts.append(
                "개선 폭이 매우 크기 때문에, 남은 핵심은 다음 분기에도 수익성과 현금 창출력이 "
                "유지되는지입니다."
            )
    elif rev_g is not None and op_g is not None and rev_g < 0 and op_g < 0:
        parts.append(
            f"{name}은 전년 동기 기준 외형과 이익이 함께 약화된 구간으로 판단됩니다. "
            "단기적으로는 마진·현금흐름이 추가로 악화되는지 여부가 해석을 가릅니다."
        )
    elif rev_op.get("directions_aligned") is False:
        parts.append(
            f"{name}은 매출과 이익의 방향이 어긋나 단일 지표로 좋거나 나쁘다고 단정하기 어렵습니다. "
            "현재로서는 외형·수익성·현금흐름을 분리해 보는 것이 타당합니다."
        )
    else:
        parts.append(
            f"{name}의 재무는 개별 지표보다 지표 간 동행과 변화 방향을 중심으로 "
            "해석하는 것이 적절합니다."
        )

    if industry and industry != "일반":
        parts.append(
            f"업종은 {industry}로, "
            f"자본집약도({industry_ctx.get('capital_intensity') or '참고 제한'})와 "
            "업종 유동성·수익성 특성을 함께 반영했습니다."
        )

    parts.append(f"현재 가장 중요한 논점은 '{key_variable}'입니다.")
    return " ".join(parts)

def _finalize_analysis(
    raw: dict[str, Any],
    *,
    company: Company,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(raw)
    payload["_company_name"] = company.company_name
    payload["_snapshot"] = snapshot
    return _normalize_result(payload, data_as_of=snapshot.get("period"))



def build_input_snapshot(
    company: Company, indicators: dict[str, Any], industry_ctx: dict[str, Any]
) -> dict[str, Any]:
    from services.financial_data import period_kind, period_label_ko

    latest = indicators.get("latest") or {}
    growth = indicators.get("growth") or {}
    trend = indicators.get("trend") or []
    yoy_comparisons = indicators.get("yoy_comparisons") or []
    series_by_kind = indicators.get("series_by_kind") or {}
    comparison_rules = indicators.get("comparison_rules") or {}
    profile = industry_ctx.get("profile") or {}

    insights = build_analysis_insights(
        indicators,
        capital_intensity=profile.get("capital_intensity"),
        period_kind_fn=period_kind,
        period_label_fn=period_label_ko,
        profile=profile,
        company_industry=company.industry,
    )

    trend_points = []
    for t in trend[:8]:
        trend_points.append(
            {
                "period": t.get("period"),
                "period_label": period_label_ko(str(t.get("period") or "")),
                "period_kind": period_kind(str(t.get("period") or "")),
                "revenue": t.get("revenue"),
                "operating_income": t.get("operating_income"),
                "operating_margin": t.get("operating_margin"),
                "roe": t.get("roe"),
                "roic": t.get("roic"),
                "debt_ratio": t.get("debt_ratio"),
                "current_ratio": t.get("current_ratio"),
                "operating_cash_flow": t.get("operating_cash_flow"),
                "fcf": t.get("fcf"),
                "revenue_growth_yoy": t.get("revenue_growth"),
                "operating_income_growth_yoy": t.get("operating_income_growth"),
                "growth_base_period": t.get("growth_base_period"),
                "growth_comparison_type": t.get("growth_comparison_type"),
            }
        )

    return {
        "period": latest.get("period"),
        "period_label": period_label_ko(str(latest.get("period") or "")),
        "periods": [t.get("period") for t in trend],
        # 원본 수치 (화면에도 있으므로 분석 문장에서 불필요 반복 금지)
        "raw_metrics": {
            "revenue": latest.get("revenue"),
            "operating_income": latest.get("operating_income"),
            "net_income": latest.get("net_income"),
            "operating_cash_flow": latest.get("operating_cash_flow"),
            "fcf": latest.get("fcf"),
            "roe": latest.get("roe"),
            "roic": latest.get("roic"),
            "operating_margin": latest.get("operating_margin"),
            "debt_ratio": latest.get("debt_ratio"),
            "current_ratio": latest.get("current_ratio"),
            "interest_coverage": latest.get("interest_coverage"),
        },
        # 하위 호환
        "latest_metrics": {
            "revenue": latest.get("revenue"),
            "operating_income": latest.get("operating_income"),
            "net_income": latest.get("net_income"),
            "operating_cash_flow": latest.get("operating_cash_flow"),
            "fcf": latest.get("fcf"),
            "roe": latest.get("roe"),
            "roic": latest.get("roic"),
            "operating_margin": latest.get("operating_margin"),
            "debt_ratio": latest.get("debt_ratio"),
            "current_ratio": latest.get("current_ratio"),
            "interest_coverage": latest.get("interest_coverage"),
        },
        # 사용자·AI 문장용 표시값 (계산용 raw와 분리)
        "display_metrics": build_display_metrics(
            {
                "revenue": latest.get("revenue"),
                "operating_income": latest.get("operating_income"),
                "net_income": latest.get("net_income"),
                "operating_cash_flow": latest.get("operating_cash_flow"),
                "fcf": latest.get("fcf"),
                "roe": latest.get("roe"),
                "roic": latest.get("roic"),
                "operating_margin": latest.get("operating_margin"),
                "debt_ratio": latest.get("debt_ratio"),
                "current_ratio": latest.get("current_ratio"),
                "interest_coverage": latest.get("interest_coverage"),
                "revenue_growth": growth.get("revenue_growth"),
                "operating_income_growth": growth.get("operating_income_growth"),
            }
        ),
        "growth_yoy": growth,
        "growth": growth,
        "yoy_comparisons": yoy_comparisons,
        "same_kind_sequential": insights.get("same_kind_sequential"),
        "metric_relations": insights.get("metric_relations"),
        "data_gaps": insights.get("data_gaps"),
        "analysis_flow": insights.get("analysis_flow"),
        "conclusion_first_rules": insights.get("conclusion_first_rules"),
        "growth_stage_hint": insights.get("growth_stage_hint"),
        "industry_analysis_context": insights.get("industry_analysis_context"),
        "external_evidence": insights.get("external_evidence"),
        "series_by_kind": series_by_kind,
        "comparison_rules": comparison_rules,
        "trend_points": trend_points,
        "industry": company.industry,
        "profile_key": profile.get("profile_key"),
        "capital_intensity": profile.get("capital_intensity"),
        "ai_instructions": {
            "use_backend_growth_only": True,
            "do_not_recompute_growth": True,
            "do_not_compare_mixed_period_types": True,
            "prefer_metric_relations": True,
            "avoid_repeating_raw_numbers": True,
            "overall_judgment_is_synthesis_not_summary": True,
            "conclusion_before_open_questions": True,
            "do_not_end_with_only_need_to_check": True,
            "use_industry_analysis_context": True,
            "do_not_say_consider_industry_only": True,
            "web_search_enabled": False,
            "do_not_force_three_risks": True,
            "language": "ko-KR only",
            "no_cjk_hanja": True,
            "use_display_metrics_for_numbers": True,
            "never_output_raw_large_integers": True,
            "always_suffix_percent_for_ratios": True,
        },
    }


def _pick_yoy_peer(trend: list[dict[str, Any]], latest_period: str | None) -> dict[str, Any] | None:
    """전년 동기 포인트 찾기."""
    from services.financial_data import yoy_peer_period

    if not trend or not latest_period:
        return None
    peer = yoy_peer_period(str(latest_period))
    if not peer:
        return None
    for point in trend:
        if str(point.get("period")) == peer:
            return point
    return None


def _trend_direction(values: list[float | None]) -> str:
    nums = [v for v in values if v is not None]
    if len(nums) < 2:
        return "판단 자료 부족"
    # values: 최신 → 과거 (동일 기간 유형 시계열만 전달할 것)
    newer, older = nums[0], nums[-1]
    if newer > older * 1.05:
        return "개선"
    if newer < older * 0.95:
        return "악화"
    return "횡보"


def build_rule_based_analysis(
    company: Company,
    indicators: dict[str, Any],
    industry_ctx: dict[str, Any],
) -> dict[str, Any]:
    """제공된 재무지표만으로 구조화 분석 생성 (추측·투자권유 금지)."""
    latest = indicators.get("latest") or {}
    growth = indicators.get("growth") or {}
    profile = industry_ctx.get("profile") or {}
    trend = indicators.get("trend") or []
    yoy_comparisons = indicators.get("yoy_comparisons") or []
    series_by_kind = indicators.get("series_by_kind") or {}
    period = str(latest.get("period") or "N/A")
    prior = _pick_yoy_peer(trend, period)
    from services.financial_data import period_kind, period_label_ko

    period_ko = period_label_ko(period)
    prior_ko = period_label_ko(str(prior.get("period"))) if prior else None
    insights = build_analysis_insights(
        indicators,
        capital_intensity=profile.get("capital_intensity"),
        period_kind_fn=period_kind,
        period_label_fn=period_label_ko,
        profile=profile,
        company_industry=company.industry,
    )
    relations = insights.get("metric_relations") or {}
    cr_view = relations.get("current_ratio_view") or {}
    rev_op = relations.get("revenue_vs_operating_income") or {}
    op_ocf = relations.get("operating_income_vs_ocf") or {}
    ocf_fcf = relations.get("ocf_vs_fcf") or {}
    high_g = relations.get("high_growth_caution") or {}
    industry_ctx_struct = insights.get("industry_analysis_context") or {}
    growth_stage = insights.get("growth_stage_hint") or {}

    op_margin = _as_float(latest.get("operating_margin"))
    roe = _as_float(latest.get("roe"))
    debt = _as_float(latest.get("debt_ratio"))
    current = _as_float(latest.get("current_ratio"))
    ocf = _as_float(latest.get("operating_cash_flow"))
    fcf = _as_float(latest.get("fcf"))
    op_income = _as_float(latest.get("operating_income"))
    rev_g = _as_float(rev_op.get("revenue_growth_yoy"))
    op_g = _as_float(rev_op.get("operating_income_growth_yoy"))
    prior_margin = _as_float(prior.get("operating_margin")) if prior else None
    prior_ocf = _as_float(prior.get("operating_cash_flow")) if prior else None
    prior_fcf = _as_float(prior.get("fcf")) if prior else None
    prior_debt = _as_float(prior.get("debt_ratio")) if prior else None

    industry_name = company.industry or profile.get("industry") or "일반"
    capital_intensity = profile.get("capital_intensity") or industry_ctx_struct.get("capital_intensity")
    liquidity_note = profile.get("liquidity_note") or ""
    profitability_note = profile.get("profitability_note") or ""

    # --- 재무 건전성 (업종·성장단계 실제 반영) ---
    soundness_parts: list[str] = []
    if debt is not None and debt <= 50:
        soundness_parts.append(
            "부채 부담이 낮은 편이라 단기 재무 안정성 측면에서는 여유가 있어 보입니다."
        )
        if capital_intensity and "높" in str(capital_intensity):
            soundness_parts.append(
                f"{industry_name}은 자본집약도가 {capital_intensity}인 편이라 "
                "낮은 부채가 안정성에는 도움이 되지만, 설비투자 재원을 자기자본·현금에 "
                "얼마나 의존하는지도 함께 보는 것이 타당합니다."
            )
    elif debt is not None and debt >= 150:
        soundness_parts.append(
            "부채 부담이 높은 편이라 금리·만기 환경이 악화되면 여유가 줄 수 있습니다. "
            "영업현금흐름이 이자·부채를 감당하는지가 해석의 핵심입니다."
        )
    else:
        soundness_parts.append(
            f"{industry_name} 기준으로 부채 구조는 극단적 고위험·저위험으로 단정하기보다 "
            "현금창출력과 함께 보는 편이 적절합니다."
        )

    if cr_view.get("elevated_or_extreme"):
        soundness_parts.append(
            "유동비율이 높은 편이라 단기 지급능력은 충분해 보입니다."
        )
        if liquidity_note:
            soundness_parts.append(
                f"{industry_name} 업종 특성상 {liquidity_note.rstrip('。. ')}."
            )
        soundness_parts.append(
            f"성장 단계 힌트는 '{growth_stage.get('stage_hint') or '자료 제한'}'입니다. "
            "높은 유동성이 안정성만 의미하는지, 성장 투자에 쓰이지 않은 자금 축적인지는 "
            "설비투자·연구개발 데이터가 MVP에 없어 단정하지 않습니다."
        )
    elif cr_view.get("level") == "low":
        soundness_parts.append(
            "유동성이 낮은 편이면 단기 지급 여력이 제한될 수 있어 "
            "영업현금흐름 추이와 함께 해석하는 것이 맞습니다."
        )
    else:
        soundness_parts.append(
            "유동성은 단기 지급능력 측면에서 대체로 무리 없는 구간에 가깝습니다."
        )

    if ocf is not None and ocf < 0:
        soundness_parts.append(
            "영업현금흐름이 음수이면 본업에서 현금을 만들지 못하는 구간입니다."
        )
    elif ocf_fcf.get("ocf_positive_fcf_negative"):
        soundness_parts.append(
            "영업현금은 플러스이나 자유현금흐름은 마이너스라 "
            "투자 부담이 현금 여유를 잠식하는 구조로 해석됩니다."
        )
    if prior and prior_debt is not None and debt is not None:
        if debt < prior_debt * 0.95:
            soundness_parts.append("전년 동기 대비 부채비율은 낮아지는 방향입니다.")
        elif debt > prior_debt * 1.05:
            soundness_parts.append("전년 동기 대비 부채비율은 높아지는 방향입니다.")

    # --- 수익성 ---
    profit_parts: list[str] = []
    if op_margin is not None and op_margin < 0:
        profit_parts.append(
            "본업 마진이 적자 구간에 있어 외형 성장만으로 수익성을 좋게 보기 어렵습니다."
        )
    elif op_margin is not None and op_margin >= 15:
        profit_parts.append("본업의 수익성 수준은 높은 편으로 보입니다.")
        if profitability_note:
            profit_parts.append(f"{industry_name} 특성: {profitability_note.rstrip('。. ')}.")
    elif op_margin is not None:
        profit_parts.append("본업 마진은 중간 수준으로, 전년 동기 변화와 함께 해석합니다.")
        if profitability_note:
            profit_parts.append(f"{industry_name} 참고: {profitability_note.rstrip('。. ')}.")
    else:
        profit_parts.append("영업이익률 데이터가 부족해 수익성 해석이 제한적입니다.")

    if prior and prior_margin is not None and op_margin is not None:
        if op_margin > prior_margin:
            profit_parts.append("전년 동기 대비 마진은 개선 방향입니다.")
        elif op_margin < prior_margin:
            profit_parts.append("전년 동기 대비 마진은 악화 방향입니다.")
        else:
            profit_parts.append("전년 동기와 마진 수준은 유사합니다.")

    if rev_g is not None and op_g is not None and op_g > rev_g and rev_g > 0 and op_g > 0:
        profit_parts.append(
            "영업이익 증가가 매출 증가보다 빨라 수익성 개선이 동반됐을 가능성이 있습니다."
        )
    if op_g is not None and op_g > 0 and op_margin is not None and op_margin < 0:
        profit_parts.append(
            "이익 성장률이 나아 보여도 마진이 적자이면 '개선 중'과 '흑자'를 구분해야 합니다."
        )
    if roe is not None:
        profit_parts.append(
            "자본 수익성(ROE)도 함께 보되, 단기간 수치만으로 효율을 단정하지 않습니다."
        )

    # --- 성장성 ---
    growth_parts: list[str] = []
    if rev_g is None and op_g is None:
        growth_parts.append(
            f"{period_ko} 기준 동일 기간의 전년 데이터가 없어 "
            "전년 대비 성장률을 계산할 수 없습니다."
        )
    else:
        if rev_op.get("directions_aligned") is True and rev_g is not None and rev_g > 0:
            growth_parts.append(
                f"전년 동기({prior_ko or growth.get('base_period_label')}) 기준으로 "
                "매출과 영업이익이 함께 늘어 실적 방향은 긍정적입니다."
            )
        elif rev_op.get("directions_aligned") is True and rev_g is not None and rev_g < 0:
            growth_parts.append(
                "전년 동기 기준 매출과 영업이익이 함께 줄어 "
                "수요·가격·비용 압박이 동시에 있을 수 있습니다."
            )
        elif rev_op.get("directions_aligned") is False:
            growth_parts.append(
                "전년 동기 기준 매출과 영업이익의 방향이 달라 "
                "외형과 이익을 분리해 해석해야 합니다."
            )
        if rev_g is not None:
            growth_parts.append(
                f"매출 전년 동기 성장률은 {_fmt_pct(rev_g)}"
                + (f", 영업이익은 {_fmt_pct(op_g)}" if op_g is not None else "")
                + "입니다."
            )
        if high_g.get("very_high_op_growth") or high_g.get("very_high_rev_growth"):
            growth_parts.append(
                "개선 폭이 커서 기저효과나 단기 반등 가능성을 배제할 수 없습니다. "
                "현재 데이터로는 구조적 개선이라고 단정하지 않으며, "
                f"성장 단계 힌트는 '{growth_stage.get('stage_hint')}'입니다. "
                "남은 핵심은 다음 분기 마진·현금흐름 유지 여부입니다."
            )
        else:
            growth_parts.append(
                "현재 확인 가능한 범위에서 성장은 마진·현금흐름과의 동행으로 해석합니다."
            )

    kind_key = period_kind(period)
    same_series = series_by_kind.get(kind_key) or []
    if len(same_series) >= 2:
        rev_series = [_as_float(t.get("revenue")) for t in same_series[:5]]
        growth_parts.append(
            f"동일 유형({kind_key}) 시계열 매출 추세는 {_trend_direction(rev_series)}입니다."
        )

    # --- 이익의 질 ---
    quality_parts: list[str] = []
    if op_income is None or ocf is None:
        quality_parts.append(
            "현재 제공된 데이터만으로 이익의 질을 충분히 판단하기 어렵습니다."
        )
    else:
        if op_ocf.get("same_sign") is True and op_income > 0 and ocf > 0:
            if prior_ocf is not None and ocf > prior_ocf and op_g is not None and op_g > 0:
                quality_parts.append(
                    "영업이익이 늘어나는 동시에 영업현금흐름도 전년 동기 대비 개선되어 "
                    "회계상 이익 증가가 실제 현금 창출력 개선으로 이어지고 있는 것으로 보입니다. "
                    "현재 확인 가능한 범위에서는 이익과 현금흐름의 괴리가 크지 않은 것으로 판단됩니다."
                )
            else:
                quality_parts.append(
                    "회계상 영업이익과 영업현금흐름의 부호가 같아 "
                    "이익이 현금 창출과 같은 방향을 보입니다. "
                    "다만 '양호하므로 질이 좋다'고 단순 연결하지 않고, 변화 방향의 동행을 기준으로 봅니다."
                )
        elif op_ocf.get("same_sign") is True:
            quality_parts.append(
                "영업이익과 영업현금흐름의 부호는 일치하지만, "
                "수준만으로 이익의 질을 단정하지 않고 추세 동행을 함께 봅니다."
            )
        else:
            quality_parts.append(
                "영업이익과 영업현금흐름의 방향이 달라 "
                "회계상 이익 증가가 현금 창출력 개선으로 충분히 이어졌다고 보기 어렵습니다. "
                "원인(운전자본 등)은 데이터가 없어 추측하지 않습니다."
            )
        if fcf is None:
            quality_parts.append("자유현금흐름 데이터가 부족해 투자 후 현금 여유 해석은 제한적입니다.")
        elif ocf_fcf.get("ocf_positive_fcf_negative"):
            quality_parts.append(
                "영업현금은 플러스이나 자유현금흐름은 마이너스라 "
                "투자 부담이 현금 여유를 잠식하는 구조로 해석됩니다."
            )
        elif fcf > 0:
            if prior_fcf is not None and fcf > prior_fcf:
                quality_parts.append(
                    "자유현금흐름이 플러스이고 전년 동기 대비 개선되어 "
                    "투자 후에도 현금 여유가 남는 편입니다. 한 기간만으로 지속성을 단정하지는 않습니다."
                )
            else:
                quality_parts.append(
                    "자유현금흐름이 플러스이면 투자 후에도 현금 여유가 남는 편입니다. "
                    "한 기간만으로 지속성을 단정하지는 않습니다."
                )
        else:
            quality_parts.append("자유현금흐름이 마이너스면 현금 여유 해석에 주의가 필요합니다.")

    # --- 핵심 변수 ---
    if high_g.get("very_high_op_growth") or high_g.get("very_high_rev_growth"):
        key_variable = "실적 개선의 지속 가능성(마진·현금흐름 동행)"
    elif op_margin is not None and op_margin < 0:
        key_variable = "본업 마진의 흑자 전환 여부"
    elif op_ocf.get("same_sign") is False:
        key_variable = "영업이익과 영업현금흐름의 괴리"
    elif cr_view.get("is_extreme_high"):
        key_variable = "높은 유동성과 자본 활용의 균형"
    elif debt is not None and debt >= 150:
        key_variable = "부채 부담 대비 현금창출력"
    else:
        key_variable = "수익성·성장·현금흐름의 동행 여부"

    # --- 종합 판단 (결론 우선) ---
    if rev_g is not None and op_g is not None and rev_g > 0 and op_g > 0:
        if op_ocf.get("same_sign") is True and op_income is not None and ocf is not None and op_income > 0 and ocf > 0:
            judgment = (
                f"{company.company_name}의 최근 실적 개선은 매출·영업이익 증가와 함께 "
                "영업현금흐름도 같은 방향으로 나타나, "
                "회계상 이익만 늘어난 것이 아니라 현금 창출력 개선이 동반된 것으로 판단됩니다."
            )
        else:
            judgment = (
                f"{company.company_name}의 최근 실적은 전년 동기 대비 매출과 영업이익이 함께 늘어 "
                "실적 방향은 긍정적으로 판단됩니다."
            )
        if high_g.get("very_high_op_growth") or high_g.get("very_high_rev_growth"):
            judgment += (
                " 개선 폭이 매우 크기 때문에, 남은 핵심은 다음 분기에도 수익성과 현금 창출력이 "
                "유지되는지입니다."
            )
        judgment += f" 현재 가장 중요한 논점은 '{key_variable}'입니다."
    elif rev_g is not None and op_g is not None and rev_g < 0 and op_g < 0:
        judgment = (
            f"{company.company_name}은 전년 동기 기준 외형과 이익이 함께 약화된 구간으로 판단됩니다. "
            f"핵심 논점은 '{key_variable}'입니다."
        )
    elif rev_op.get("directions_aligned") is False:
        judgment = (
            f"{company.company_name}은 매출과 이익의 방향이 어긋나 "
            "단일 지표로 단정하기 어렵습니다. "
            f"우선 확인할 논점은 '{key_variable}'입니다."
        )
    else:
        judgment = (
            f"{company.company_name}({industry_name})의 {period_ko} 재무는 "
            "지표 간 동행과 변화 방향을 중심으로 해석하는 것이 타당합니다. "
            f"가장 중요한 논점은 '{key_variable}'입니다."
        )

    # --- 강점 / 위험 (근거 있는 항목만, 3개 강제 금지) ---
    strengths: list[str] = []
    risks: list[str] = []

    if rev_g is not None and op_g is not None and rev_g > 0 and op_g > 0:
        strengths.append("전년 동기 기준 매출과 영업이익이 함께 개선되어 실적 방향이 긍정적입니다.")
    if op_margin is not None and op_margin >= 10 and (prior_margin is None or op_margin >= prior_margin):
        strengths.append("본업 수익성이 비교적 높은 수준을 유지하고 있습니다.")
    if op_ocf.get("same_sign") is True and op_income is not None and op_income > 0 and ocf is not None and ocf > 0:
        strengths.append("영업이익과 영업현금흐름이 같은 방향으로 현금 창출을 뒷받침합니다.")
    if debt is not None and debt <= 50 and (ocf is None or ocf >= 0):
        strengths.append("부채 부담이 낮아 재무 완충 여지가 상대적으로 큽니다.")

    if op_margin is not None and op_margin < 0:
        risks.append("본업 마진이 적자여서 추가 자금 소요·수익성 회복 여부를 점검해야 합니다.")
    if ocf is not None and ocf < 0:
        risks.append("영업현금흐름이 음수로 본업 현금 창출이 약한 구간입니다.")
    if rev_g is not None and op_g is not None and rev_g < 0 and op_g < 0:
        risks.append("매출·영업이익이 동반 감소해 수요 또는 가격 여력 약화 가능성을 확인해야 합니다.")
    if debt is not None and debt >= 150:
        risks.append("부채 부담이 높아 조달 환경 악화 시 실적에 영향을 줄 수 있습니다.")
    if ocf_fcf.get("ocf_positive_fcf_negative"):
        risks.append("영업현금은 양수이나 FCF가 음수로 투자 부담이 현금 여유를 잠식할 수 있습니다.")
    if high_g.get("very_high_op_growth") and (ocf is None or prior_ocf is None):
        risks.append(
            "이익 개선 폭이 큰 반면 현금흐름 동행을 충분히 확인하기 어려워 "
            "지속 가능성이 불확실합니다."
        )
    if cr_view.get("is_extreme_high"):
        risks.append(
            "유동성이 극단적으로 높아 단기 안정성과 별개로 "
            "자본 활용·성장 투자 균형이 향후 확인 포인트가 됩니다."
        )

    if not strengths:
        strengths.append(
            "제공된 지표만으로는 뚜렷한 강점을 단정하기 어렵습니다. 다년 추세 확인이 필요합니다."
        )
    if not risks:
        risks.append(
            "현재 확인 가능한 재무 데이터에서는 뚜렷한 재무 건전성 위험요인이 제한적입니다."
        )

    # --- 투자 질문 (미래 검증형, 이미 답 가능한 질문 제외) ---
    key_questions: list[dict[str, str]] = []
    if high_g.get("very_high_op_growth") or high_g.get("very_high_rev_growth"):
        key_questions.append(
            {
                "question": "최근 실적 개선이 다음 분기에도 수익성·현금흐름과 함께 지속되는가?",
                "why": (
                    f"전년 동기 매출 성장 {_fmt_pct(rev_g)}, 영업이익 성장 {_fmt_pct(op_g)}로 "
                    "개선 폭이 큽니다. 기저효과 가능성을 배제하려면 다음 공시에서 "
                    "마진·영업현금의 유지 여부를 봐야 합니다."
                ),
            }
        )
    if op_ocf.get("same_sign") is False or (
        op_g is not None and op_g > 0 and (ocf is None or (prior_ocf is not None and ocf < prior_ocf))
    ):
        key_questions.append(
            {
                "question": "영업이익 개선이 실제 현금 창출력 개선으로 이어지고 있는가?",
                "why": (
                    f"현재 영업이익과 영업현금의 관계 해석이 "
                    f"{op_ocf.get('interpretation')}입니다. "
                    "다음 공시에서 두 지표의 동행 여부가 이익의 질 판단의 분기점입니다."
                ),
            }
        )
    if op_margin is not None and op_margin < 0:
        key_questions.append(
            {
                "question": "다음 공시에서 본업 마진이 흑자로 전환되거나 적자 폭이 줄어드는가?",
                "why": (
                    f"{period_ko} 기준 영업이익률이 음수입니다. "
                    "성장률만으로 수익성 회복을 단정할 수 없어 마진 부호 변화가 핵심입니다."
                ),
            }
        )
    elif op_margin is not None and op_margin >= 10:
        key_questions.append(
            {
                "question": "현재의 높은 수익성이 일시적 반등인지 지속 가능한 개선인지 확인할 수 있는가?",
                "why": (
                    f"{period_ko} 본업 마진이 높은 편입니다. "
                    "한 기간 수준만으로는 지속성을 확정할 수 없어 다음 공시 유지 여부가 중요합니다."
                ),
            }
        )
    if cr_view.get("elevated_or_extreme"):
        key_questions.append(
            {
                "question": "높은 유동성이 유지되는 가운데 자본 활용·성장 투자 균형은 어떻게 변하는가?",
                "why": (
                    f"유동비율 수준이 {cr_view.get('level')}로 분류됩니다. "
                    "단기 지급능력은 충분할 수 있으나 재투자 효율은 데이터가 없어 단정할 수 없고 "
                    "향후 공시에서 확인할 필요가 있습니다."
                ),
            }
        )
    if len(key_questions) < 2:
        key_questions.append(
            {
                "question": "현재의 재무 안정성과 수익성 조합이 다음 공시에서도 유지되는가?",
                "why": (
                    f"{period_ko} 기준으로는 방향 해석이 가능하지만, "
                    "지속 여부는 다음 기간 마진·현금흐름·레버리지 변화로만 검증할 수 있습니다."
                ),
            }
        )

    # --- 앞으로 확인할 데이터 (변화 확인형) ---
    data_to_watch: list[str] = []
    if high_g.get("very_high_op_growth") or high_g.get("very_high_rev_growth"):
        data_to_watch.append("다음 분기 전년 동기 매출·영업이익 성장률의 유지·둔화 여부")
    data_to_watch.append("다음 분기 영업이익률 유지·개선 여부")
    data_to_watch.append("영업이익 변화와 영업현금흐름 변화의 동반 여부")
    if fcf is not None:
        data_to_watch.append("FCF의 지속적인 플러스(또는 적자 축소) 여부")
    if cr_view.get("elevated_or_extreme"):
        data_to_watch.append("높은 유동성 지속 여부와 자본 활용 관련 공시 변화")
    if debt is not None and debt >= 100:
        data_to_watch.append("부채비율·이자보상 여력의 추가 악화 여부")
    data_to_watch = data_to_watch[:5]

    payload = {
        "overall_judgment": judgment,
        "key_variable": key_variable,
        "financial_soundness": " ".join(soundness_parts),
        "profitability": " ".join(profit_parts),
        "growth": " ".join(growth_parts),
        "earnings_quality": " ".join(quality_parts),
        "strengths": strengths[:3],
        "risks": risks[:3],
        "key_questions": key_questions[:3],
        "data_to_watch": data_to_watch,
    }
    snap_for_finalize = {
        "metric_relations": relations,
        "industry_analysis_context": industry_ctx_struct,
        "growth_stage_hint": growth_stage,
        "external_evidence": insights.get("external_evidence"),
        "raw_metrics": {
            "revenue": latest.get("revenue"),
            "operating_income": latest.get("operating_income"),
            "net_income": latest.get("net_income"),
            "operating_cash_flow": latest.get("operating_cash_flow"),
            "fcf": latest.get("fcf"),
            "roe": latest.get("roe"),
            "roic": latest.get("roic"),
            "operating_margin": latest.get("operating_margin"),
            "debt_ratio": latest.get("debt_ratio"),
            "current_ratio": latest.get("current_ratio"),
        },
        "growth": growth,
        "growth_yoy": growth,
    }
    return _finalize_analysis(payload, company=company, snapshot=snap_for_finalize)


def _system_prompt() -> str:
    return """당신은 기업 재무 분석 보조 AI다. 투자 권유(매수/매도)는 금지한다.
목표는 사용자가 기업을 분석하도록 돕는 것이다. 의문만 남기고 끝내지 마라.

[결론 우선 원칙 — 가장 중요]
1) 현재 재무·업종 데이터로 판단 가능한 것은 반드시 결론을 내린다. ("판단됩니다", "동반된 것으로 보입니다")
2) 확정할 수 없는 항목만 잔여 확인 포인트로 남긴다.
3) "확인해야 합니다/판단할 필요가 있습니다"만으로 종합 판단을 끝내지 마라.
4) external_evidence.web_search_enabled=false 이므로 공시·뉴스·수주·신제품·일회성 원인을 추측하지 마라.
5) 검색 결과가 없으면 "확인할 수 없다"고 밝히고 재무 결론에 집중한다.

나쁜 종합 판단:
"최근 실적 개선이 일시적 반등인지 구조적 개선인지 수익성·현금흐름으로 확인해야 합니다."

좋은 종합 판단:
"최근 실적 개선은 매출·영업이익 증가와 영업현금흐름이 같은 방향으로 나타나 현금 창출력 개선이 동반된 것으로 판단됩니다. 개선 폭이 커 다음 분기 유지 여부가 남은 핵심입니다."

[분석 순서]
원본 수치 → 전년 동기 변화 → 지표 간 관계 → (업종·성장단계 프로필) → 결론 → 잔여 확인 포인트 → 투자 질문

[섹션 역할]
1) overall_judgment: 상위 결론 2~4문장. 수치 나열·세부 섹션 복사 금지. 결론 먼저.
2) key_variable: 핵심 논점 1개
3) financial_soundness: 부채·유동성·현금 + industry_analysis_context를 실제 문장에 반영.
   - "업종 특성을 고려할 필요가 있습니다"만 쓰는 것 금지.
   - 업종명, capital_intensity, liquidity_note를 활용해 구체화.
4) profitability: 마진·ROE 의미와 변화. profitability_note 반영 가능.
5) growth: 매출·이익 동행 + growth_stage_hint. 고성장=무조건 좋음 금지.
6) earnings_quality: 이익↔영업현금↔FCF 동행. "둘 다 양호하니 질이 좋다" 금지.
7) strengths / risks: 데이터 근거만. 위험 3개 강제 금지.
8) key_questions: 미래 검증형만 1~3개
9) data_to_watch: "무엇을 확인해야 하는가" 형태

[유동비율]
elevated/extreme_high: 지급능력은 충분하다고 먼저 결론. 이어서 업종 자본집약·성장단계 힌트로 자본 활용 관점을 서술.
재투자 부족 단정 금지. R&D/설비투자 데이터 없으면 없다고 명시.

[언어 — 강제]
자연스러운 한국어만. 한자(能力, 良好, 優秀, 資本 등)·중국어·일본어 금지.
영문은 ROE, FCF, API 필드 등 필요 시에만.

[숫자 표시 — 강제]
- 금액·비율을 쓸 때는 financial_snapshot.display_metrics 값을 우선 사용한다.
- 원시 큰 정수(예: 23147103000000.0)를 문장에 쓰지 않는다. → "23.15조원"
- 모든 비율(부채비율·유동비율·ROE·ROIC·영업이익률·성장률)은 반드시 %를 붙인다. (예: 253.91%)
- %가 이미 있으면 중복하지 않는다.
- 금액과 비율을 혼동하지 않는다.

[기간]
yoy_comparisons만 전년 동기. 분기·반기·연간 혼용 금지.

반드시 JSON만 출력:
{
  "overall_judgment": "...",
  "key_variable": "...",
  "financial_soundness": "...",
  "profitability": "...",
  "growth": "...",
  "earnings_quality": "...",
  "strengths": ["..."],
  "risks": ["..."],
  "key_questions": [{"question": "...", "why": "..."}],
  "data_to_watch": ["..."],
  "data_as_of": "기준 기간"
}"""


def _user_prompt(company: Company, industry_ctx: dict[str, Any], snapshot: dict[str, Any]) -> str:
    return json.dumps(
        {
            "company": {
                "company_id": company.company_id,
                "company_name": company.company_name,
                "industry": company.industry,
            },
            "industry_context": {
                "prompt_text": industry_ctx.get("prompt_text"),
                "prompt_hints": industry_ctx.get("prompt_hints"),
                "profile": {
                    "profile_key": (industry_ctx.get("profile") or {}).get("profile_key"),
                    "capital_intensity": (industry_ctx.get("profile") or {}).get("capital_intensity"),
                    "liquidity_note": (industry_ctx.get("profile") or {}).get("liquidity_note"),
                    "profitability_note": (industry_ctx.get("profile") or {}).get("profitability_note"),
                    "revenue_structure": (industry_ctx.get("profile") or {}).get("revenue_structure"),
                    "metric_hints": (industry_ctx.get("profile") or {}).get("metric_hints"),
                    "analysis_rules": (industry_ctx.get("profile") or {}).get("analysis_rules"),
                },
            },
            "financial_snapshot": {
                "period": snapshot.get("period"),
                "period_label": snapshot.get("period_label"),
                "raw_metrics": snapshot.get("raw_metrics") or snapshot.get("latest_metrics"),
                "display_metrics": snapshot.get("display_metrics"),
                "growth_yoy": snapshot.get("growth_yoy") or snapshot.get("growth"),
                "yoy_comparisons": snapshot.get("yoy_comparisons"),
                "same_kind_sequential": snapshot.get("same_kind_sequential"),
                "metric_relations": snapshot.get("metric_relations"),
                "growth_stage_hint": snapshot.get("growth_stage_hint"),
                "industry_analysis_context": snapshot.get("industry_analysis_context"),
                "external_evidence": snapshot.get("external_evidence"),
                "data_gaps": snapshot.get("data_gaps"),
                "analysis_flow": snapshot.get("analysis_flow"),
                "conclusion_first_rules": snapshot.get("conclusion_first_rules"),
                "series_by_kind": snapshot.get("series_by_kind"),
                "comparison_rules": snapshot.get("comparison_rules"),
                "trend_points": snapshot.get("trend_points"),
                "ai_instructions": snapshot.get("ai_instructions"),
            },
            "writing_rules": [
                "종합 판단: 결론 먼저, '확인 필요'만으로 끝내지 말 것",
                "업종: industry_analysis_context를 구체 문장에 반영 ('고려 필요'만 금지)",
                "외부 검색 미연결: 실적 원인을 추측하지 말 것",
                "이익의 질: 동행·괴리로 해석, 양호=질 좋음 단순 연결 금지",
                "숫자는 display_metrics 사용 (원시 큰 정수 금지, 비율은 반드시 %)",
                "한자·중국어·일본어 금지",
                "자연스러운 한국어만",
            ],
        },
        ensure_ascii=False,
    )





def get_cached(session: Session, company_id: str, cache_key: str) -> AnalysisCache | None:
    stmt = (
        select(AnalysisCache)
        .where(AnalysisCache.company_id == company_id)
        .where(AnalysisCache.cache_key == cache_key)
    )
    return session.exec(stmt).first()


def save_cache(
    session: Session,
    *,
    company_id: str,
    cache_key: str,
    source: str,
    result: dict[str, Any],
) -> None:
    row = get_cached(session, company_id, cache_key)
    payload = json.dumps(result, ensure_ascii=False)
    if row is None:
        session.add(
            AnalysisCache(
                company_id=company_id,
                cache_key=cache_key,
                source=source,
                result_json=payload,
                created_at=datetime.utcnow(),
            )
        )
    else:
        row.source = source
        row.result_json = payload
        row.created_at = datetime.utcnow()
    session.commit()


def analyze_company(
    session: Session,
    company_id: str,
    years: int = 5,
    force_refresh: bool = False,
) -> dict[str, Any]:
    company = session.get(Company, company_id)
    if company is None:
        raise LookupError("기업을 찾을 수 없습니다.")

    try:
        from services.industry_resolve import ensure_company_industry

        # 업종 Groq는 분석 API 호출과 경합하지 않도록 DART만 사용
        ensure_company_industry(session, company, allow_groq=False)
        session.refresh(company)
    except Exception:  # noqa: BLE001
        logger.exception("analyze industry resolve error")

    items, fin_message = get_or_load_financials(session, company_id, years=years)
    if not items:
        raise LookupError(fin_message or "분석에 필요한 재무 데이터가 없습니다.")

    indicators = build_indicators_payload(items)
    industry_ctx = build_analysis_context(company, indicators)
    snapshot = build_input_snapshot(company, indicators, industry_ctx)
    key = _cache_key(company_id, snapshot)

    from config import reload_env, settings

    reload_env()
    provider = settings.analysis_provider
    desired_source = (
        provider if provider in {"rule", "groq", "gemini", "openai"} else "rule"
    )

    if not force_refresh:
        cached = get_cached(session, company_id, key)
        if cached is not None and cached.source == desired_source:
            try:
                cached_analysis = _normalize_result(
                    json.loads(cached.result_json),
                    data_as_of=snapshot.get("period"),
                )
            except (ValueError, json.JSONDecodeError, TypeError):
                cached_analysis = None
            if cached_analysis is not None:
                notice, message = _split_status_text(fin_message)
                return {
                    "company_id": company.company_id,
                    "company_name": company.company_name,
                    "industry": company.industry,
                    "source": cached.source,
                    "cached": True,
                    "analysis": cached_analysis,
                    "input_snapshot": snapshot,
                    "message": message,
                    "notice": notice,
                }

    notice, message = _split_status_text(fin_message)
    source = "rule"
    analysis: dict[str, Any]

    if settings.use_groq_analysis:
        client = GroqClient()
        if client.has_key:
            try:
                raw = client.chat_json(
                    _system_prompt(),
                    _user_prompt(company, industry_ctx, snapshot),
                )
                analysis = _finalize_analysis(raw, company=company, snapshot=snapshot)
                source = "groq"
            except (GroqError, ValueError) as exc:
                logger.warning("Groq 분석 실패, rule 폴백: %s", exc)
                analysis = build_rule_based_analysis(company, indicators, industry_ctx)
                source = "rule"
        else:
            logger.warning("ANALYSIS_PROVIDER=groq 이지만 GROQ_API_KEY 미설정 - rule 사용")
            analysis = build_rule_based_analysis(company, indicators, industry_ctx)
            source = "rule"
    elif settings.use_gemini_analysis:
        client = GeminiClient()
        if client.has_key:
            try:
                raw = client.chat_json(
                    _system_prompt(),
                    _user_prompt(company, industry_ctx, snapshot),
                )
                analysis = _finalize_analysis(raw, company=company, snapshot=snapshot)
                source = "gemini"
            except (GeminiError, ValueError) as exc:
                logger.warning("Gemini 분석 실패, rule 폴백: %s", exc)
                analysis = build_rule_based_analysis(company, indicators, industry_ctx)
                source = "rule"
        else:
            logger.warning("ANALYSIS_PROVIDER=gemini 이지만 GEMINI_API_KEY 미설정 - rule 사용")
            analysis = build_rule_based_analysis(company, indicators, industry_ctx)
            source = "rule"
    elif settings.use_openai_analysis:
        client = OpenAIClient()
        if client.has_key:
            try:
                raw = client.chat_json(
                    _system_prompt(),
                    _user_prompt(company, industry_ctx, snapshot),
                )
                analysis = _finalize_analysis(raw, company=company, snapshot=snapshot)
                source = "openai"
            except (OpenAIError, ValueError) as exc:
                logger.warning("OpenAI 분석 실패, rule 폴백: %s", exc)
                analysis = build_rule_based_analysis(company, indicators, industry_ctx)
                source = "rule"
        else:
            logger.warning("ANALYSIS_PROVIDER=openai 이지만 OPENAI_API_KEY 미설정 - rule 사용")
            analysis = build_rule_based_analysis(company, indicators, industry_ctx)
            source = "rule"
    else:
        analysis = build_rule_based_analysis(company, indicators, industry_ctx)
        source = "rule"

    save_cache(session, company_id=company_id, cache_key=key, source=source, result=analysis)

    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "industry": company.industry,
        "source": source,
        "cached": False,
        "analysis": analysis,
        "input_snapshot": snapshot,
        "message": message,
        "notice": notice,
    }
