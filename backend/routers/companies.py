"""기업 검색·기본정보·재무·지표 API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from database import get_session
from schemas.analysis import AnalysisResponse, AnalysisResult
from schemas.company import CompanyOut, CompanySearchResponse
from schemas.dashboard import DashboardResponse
from schemas.financial import FinancialListResponse, FinancialPeriodOut
from schemas.indicators import GrowthOut, IndicatorPoint, IndicatorsResponse
from schemas.industry import IndustryContextResponse, IndustryProfileOut
from services import company_master as cm
from services import dashboard as dash
from services import financial_analysis as fa
from services import financial_data as fd
from services import industry_profile as ip
from services.dart_client import DartApiError
from services.dart_corp_code import DartCorpCodeError
from services.financial_indicators import build_indicators_payload
from services.gemini_client import GeminiError
from services.groq_client import GroqError
from services.openai_client import OpenAIError

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/search", response_model=CompanySearchResponse)
def search_companies(
    q: str = Query(..., min_length=1, description="기업명 또는 종목코드"),
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
):
    items = cm.search_companies(session, q, limit=limit)
    return CompanySearchResponse(
        query=q.strip(),
        total=len(items),
        items=[CompanyOut.model_validate(c) for c in items],
    )


@router.post("/master/sync")
def sync_company_master(session: Session = Depends(get_session)):
    """DART 상장사 목록을 Company Master에 동기화한다."""
    try:
        return cm.sync_listed_companies_from_dart(session)
    except DartCorpCodeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{company_id}/financials", response_model=FinancialListResponse)
def get_company_financials(
    company_id: str,
    years: int = Query(5, ge=1, le=10),
    refresh: bool = Query(False, description="true면 DART/seed로 다시 동기화"),
    session: Session = Depends(get_session),
):
    try:
        items, message = fd.get_or_load_financials(
            session,
            company_id,
            years=years,
            force_sync=refresh,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DartApiError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"DART API 오류 [{exc.status}] {exc.message}",
        ) from exc

    if not items:
        raise HTTPException(
            status_code=404,
            detail=message or "재무 데이터를 찾을 수 없습니다.",
        )

    return FinancialListResponse(
        company_id=company_id,
        total=len(items),
        items=[FinancialPeriodOut(**item) for item in items],
        message=message,
    )


@router.get("/{company_id}/indicators", response_model=IndicatorsResponse)
def get_company_indicators(
    company_id: str,
    years: int = Query(5, ge=2, le=10, description="추세에 포함할 연도 수 (3~5 권장)"),
    session: Session = Depends(get_session),
):
    try:
        items, message = fd.get_or_load_financials(session, company_id, years=years)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DartApiError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"DART API 오류 [{exc.status}] {exc.message}",
        ) from exc

    if not items:
        raise HTTPException(
            status_code=404,
            detail=message or "지표 계산에 필요한 재무 데이터가 없습니다.",
        )

    payload = build_indicators_payload(items)
    latest = payload["latest"]
    growth = payload["growth"]

    return IndicatorsResponse(
        company_id=company_id,
        periods=payload["periods"],
        latest=IndicatorPoint(**latest) if latest else None,
        growth=GrowthOut(**growth) if growth else None,
        trend=[IndicatorPoint(**p) for p in payload["trend"]],
        message=message,
    )


@router.get("/{company_id}/industry-context", response_model=IndustryContextResponse)
def get_company_industry_context(
    company_id: str,
    years: int = Query(5, ge=2, le=10),
    session: Session = Depends(get_session),
):
    """업종 프로필 + 지표 요약을 AI 분석용 컨텍스트로 반환."""
    company = cm.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")

    from services.industry_resolve import ensure_company_industry

    ensure_company_industry(session, company, allow_groq=True)
    session.refresh(company)

    message = None
    indicators_payload: dict = {}
    try:
        items, message = fd.get_or_load_financials(session, company_id, years=years)
        if items:
            indicators_payload = build_indicators_payload(items)
    except DartApiError as exc:
        message = f"지표 로드 실패: [{exc.status}] {exc.message}"

    ctx = ip.build_analysis_context(company, indicators_payload or None)
    return IndustryContextResponse(
        company_id=ctx["company_id"],
        company_name=ctx["company_name"],
        industry=ctx["industry"],
        profile=IndustryProfileOut(**ctx["profile"]),
        indicators_latest=ctx["indicators_latest"],
        indicators_growth=ctx["indicators_growth"],
        trend_periods=ctx["trend_periods"],
        prompt_hints=ctx["prompt_hints"],
        prompt_text=ctx["prompt_text"],
        message=message,
    )


@router.get("/{company_id}/dashboard", response_model=DashboardResponse)
def get_company_dashboard(
    company_id: str,
    years: int = Query(5, ge=2, le=10),
    refresh: bool = Query(False, description="true면 분석 캐시 무시"),
    session: Session = Depends(get_session),
):
    """기본정보 + 재무 + 지표/추세 + 업종 + 분석을 한 번에 반환."""
    try:
        return dash.build_dashboard(
            session,
            company_id,
            years=years,
            refresh_analysis=refresh,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{company_id}/analysis", response_model=AnalysisResponse)
def get_company_analysis(
    company_id: str,
    years: int = Query(5, ge=2, le=10),
    refresh: bool = Query(False, description="true면 캐시 무시 후 재분석"),
    session: Session = Depends(get_session),
):
    try:
        result = fa.analyze_company(
            session,
            company_id,
            years=years,
            force_refresh=refresh,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DartApiError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"DART API 오류 [{exc.status}] {exc.message}",
        ) from exc
    except (GroqError, GeminiError, OpenAIError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AnalysisResponse(
        company_id=result["company_id"],
        company_name=result["company_name"],
        industry=result["industry"],
        source=result["source"],
        cached=result["cached"],
        analysis=AnalysisResult(**result["analysis"]),
        input_snapshot=result["input_snapshot"],
        message=result.get("message"),
        notice=result.get("notice"),
    )


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: str,
    resolve_industry: bool = Query(
        True, description="미분류일 때 DART/Groq로 업종 보강"
    ),
    session: Session = Depends(get_session),
):
    company = cm.get_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="기업을 찾을 수 없습니다.")
    if resolve_industry:
        from services.industry_resolve import ensure_company_industry

        ensure_company_industry(session, company, allow_groq=True)
        session.refresh(company)
    return CompanyOut.model_validate(company)
