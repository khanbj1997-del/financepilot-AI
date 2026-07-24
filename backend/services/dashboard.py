"""기업 분석 Dashboard 통합 조립."""
from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from schemas.analysis import AnalysisResult
from schemas.company import CompanyOut
from schemas.dashboard import DashboardResponse, DashboardSectionStatus
from schemas.financial import FinancialPeriodOut
from schemas.indicators import GrowthOut, IndicatorPoint
from schemas.industry import IndustryProfileOut
from services import company_master as cm
from services import financial_analysis as fa
from services import financial_data as fd
from services import industry_profile as ip
from services.dart_client import DartApiError
from services.financial_indicators import build_indicators_payload
from services.gemini_client import GeminiError
from services.groq_client import GroqError
from services.openai_client import OpenAIError

logger = logging.getLogger(__name__)


def _is_provider_noise(text: str | None) -> bool:
    """분석 provider/쿼터 등 사용자에게 보여줄 필요 없는 안내·경고."""
    if not text:
        return True
    lowered = text.lower()
    keys = (
        "gemini",
        "groq",
        "openai",
        "analysis_provider",
        "quota",
        "http 429",
        "resource_exhausted",
        "크레딧",
        "rule 폴백",
        "규칙 기반 분석 사용",
    )
    return any(k in lowered for k in keys)


def build_dashboard(
    session: Session,
    company_id: str,
    years: int = 5,
    refresh_analysis: bool = False,
) -> DashboardResponse:
    """
    기본정보 + 재무 + 지표/추세 + 업종 + 분석을 한 응답으로 모은다.

    부분 실패 정책:
    - 기업 없음 → LookupError (라우터에서 404)
    - 재무/지표 실패 → 해당 섹션만 비우고 warnings에 기록, 200 유지
    - 분석 실패 → analysis=null + warning, 나머지 섹션은 반환
    - 로컬 rule 모드 안내는 notices로 분리 (warnings에 넣지 않음)
    """
    warnings: list[str] = []
    notices: list[str] = []
    sections = DashboardSectionStatus()

    company = cm.get_company(session, company_id)
    if company is None:
        raise LookupError("기업을 찾을 수 없습니다.")

    # 업종 미분류일 때만 DART 기업개황 → (필요 시) Groq 추정
    try:
        from services.industry_resolve import ensure_company_industry

        # Dashboard에서도 업종은 DART만. 분석용 Groq 쿼터를 우선 확보한다.
        ensure_company_industry(session, company, allow_groq=False)
        session.refresh(company)
    except Exception:  # noqa: BLE001
        logger.exception("dashboard industry resolve error")

    company_out = CompanyOut.model_validate(company)
    sections.company = True

    financial_items: list[dict[str, Any]] = []
    fin_message = None
    try:
        financial_items, fin_message = fd.get_or_load_financials(
            session, company_id, years=years, force_sync=refresh_analysis
        )
        notice, warn = fa._split_status_text(fin_message)
        if notice:
            notices.append(notice)
        if warn:
            warnings.append(warn)
    except DartApiError as exc:
        warnings.append(f"재무 데이터 로드 실패: [{exc.status}] {exc.message}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("dashboard financials error")
        warnings.append(f"재무 데이터 로드 실패: {exc}")

    financials_out: list[FinancialPeriodOut] = []
    if financial_items:
        financials_out = [FinancialPeriodOut(**item) for item in financial_items]
        sections.financials = True
    else:
        warnings.append("재무 데이터가 없어 지표·분석이 제한됩니다.")

    latest = None
    growth = None
    trend: list[IndicatorPoint] = []
    trend_quarterly: list[IndicatorPoint] = []
    trend_basis = None
    statement_type = None
    preferred_fs = None
    if financial_items:
        try:
            all_sorted, annual_items, interim_items, preferred_fs = (
                fd.split_latest_and_annual(financial_items)
            )
            statement_type = "연결" if preferred_fs == "CFS" else "개별"

            latest_payload = build_indicators_payload(all_sorted)
            if latest_payload.get("latest"):
                latest = IndicatorPoint(**latest_payload["latest"])
                sections.indicators = True

            if annual_items:
                annual_payload = build_indicators_payload(annual_items)
                if annual_payload.get("growth"):
                    growth = GrowthOut(**annual_payload["growth"])
                trend = [IndicatorPoint(**p) for p in annual_payload.get("trend") or []]
                trend_basis = "annual"
            else:
                trend_basis = "interim_only"
                notices.append(
                    "연간 공시가 부족합니다. 분기 탭에서 추세를 확인하세요."
                )

            if interim_items:
                q_payload = build_indicators_payload(interim_items)
                trend_quarterly = [
                    IndicatorPoint(**p) for p in q_payload.get("trend") or []
                ]
                if not annual_items and q_payload.get("growth"):
                    growth = GrowthOut(**q_payload["growth"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("dashboard indicators error")
            warnings.append(f"지표 계산 실패: {exc}")

    industry_profile = None
    try:
        profile = ip.get_profile_for_company(company)
        industry_profile = IndustryProfileOut(**profile)
        sections.industry = True
    except Exception as exc:  # noqa: BLE001
        logger.exception("dashboard industry error")
        warnings.append(f"업종 프로필 로드 실패: {exc}")

    analysis = None
    analysis_source = None
    analysis_cached = False
    if financial_items:
        try:
            result = fa.analyze_company(
                session,
                company_id,
                years=years,
                force_refresh=refresh_analysis,
            )
            analysis = AnalysisResult(**result["analysis"])
            analysis_source = result.get("source")
            analysis_cached = bool(result.get("cached"))
            sections.analysis = True
            if result.get("message") and not _is_provider_noise(result.get("message")):
                warnings.append(result["message"])
            if result.get("notice") and not _is_provider_noise(result.get("notice")):
                notices.append(result["notice"])
        except LookupError as exc:
            warnings.append(f"분석 생략: {exc}")
        except (DartApiError, GroqError, GeminiError, OpenAIError) as exc:
            logger.warning("dashboard analysis provider/api error: %s", exc)
            # 사용자에게 LLM/쿼터 상세는 숨기고, 재무 섹션은 유지
        except Exception as exc:  # noqa: BLE001
            logger.exception("dashboard analysis error")
            warnings.append("분석 결과를 불러오지 못했습니다.")
    else:
        warnings.append("분석 생략: 재무 데이터 없음")

    def _uniq(items: list[str]) -> list[str]:
        out: list[str] = []
        for item in items:
            if item and item not in out:
                out.append(item)
        return out

    uniq_warnings = _uniq(warnings)
    uniq_notices = _uniq(notices)

    ready = sections.company and sections.financials and sections.indicators
    if ready and sections.analysis:
        message = "Dashboard 데이터 준비 완료"
    elif ready:
        message = "핵심 재무·지표는 준비됐고, 분석 섹션만 부분 실패/생략되었습니다."
    else:
        message = "일부 섹션만 준비되었습니다. warnings를 확인하세요."

    return DashboardResponse(
        company_id=company_id,
        company=company_out,
        financials=financials_out,
        indicators=latest,
        growth=growth,
        trend=trend,
        trend_quarterly=trend_quarterly,
        industry_profile=industry_profile,
        analysis=analysis,
        analysis_source=analysis_source,
        analysis_cached=analysis_cached,
        sections=sections,
        warnings=uniq_warnings,
        notices=uniq_notices,
        message=message,
        meta={
            "years": years,
            "partial": not (ready and sections.analysis),
            "analysis_provider": analysis_source,
            "trend_basis": trend_basis if financial_items else None,
            "fs_div": preferred_fs if financial_items else None,
            "statement_type": statement_type if financial_items else None,
        },
    )
