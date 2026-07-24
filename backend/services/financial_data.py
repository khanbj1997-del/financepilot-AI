"""재무 데이터 수집·저장·조회 (연간 + 분기, CFS→OFS 폴백)."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from models.company import Company
from models.financial import FinancialData
from services.dart_client import DartApiError, DartClient
from services.financial_parser import extract_metrics_from_dart_rows

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "financials_seed.json"
DEFAULT_YEARS = 5

# 분기 보고서 (최신 스냅샷용)
INTERIM_SPECS: list[tuple[str, str]] = [
    ("11014", "Q3"),
    ("11012", "H1"),
    ("11013", "Q1"),
]


def period_label(year: int, suffix: str) -> str:
    return f"{year}{suffix}" if suffix else str(year)


def is_annual_period(period: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", (period or "").strip()))


def parse_period_parts(period: str) -> tuple[int | None, str]:
    """
    기간 파싱 → (연도, 유형).
    유형: FY | Q1 | H1 | Q3 | UNKNOWN
    """
    text = (period or "").strip().upper()
    m = re.fullmatch(r"(\d{4})(Q1|H1|Q3)?", text)
    if not m:
        return None, "UNKNOWN"
    year = int(m.group(1))
    tag = m.group(2) or "FY"
    return year, tag


def period_kind(period: str) -> str:
    """기간 유형만 반환 (FY/Q1/H1/Q3/UNKNOWN)."""
    return parse_period_parts(period)[1]


def yoy_peer_period(period: str) -> str | None:
    """전년 동기 기간 라벨. 예: 2026Q1→2025Q1, 2025→2024."""
    year, kind = parse_period_parts(period)
    if year is None or kind == "UNKNOWN":
        return None
    if kind == "FY":
        return str(year - 1)
    return f"{year - 1}{kind}"


def period_label_ko(period: str) -> str:
    """UI·프롬프트용 한국어 기간 표기."""
    year, kind = parse_period_parts(period)
    if year is None:
        return str(period or "")
    if kind == "FY":
        return f"{year}년 연간"
    if kind == "Q1":
        return f"{year}년 1분기"
    if kind == "H1":
        return f"{year}년 반기"
    if kind == "Q3":
        return f"{year}년 3분기"
    return str(period)


def period_sort_key(period: str) -> tuple[int, int]:
    """기간 정렬 키. 클수록 최신. Q1=1, H1=2, Q3=3, 연간=4."""
    year, kind = parse_period_parts(period)
    if year is None:
        text = (period or "").strip()
        try:
            return (int(text[:4]), 0)
        except ValueError:
            return (0, 0)
    quarter = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}.get(kind, 0)
    return (year, quarter)


def _metrics_to_json(metrics: dict) -> str:
    return json.dumps(metrics, ensure_ascii=False)


def _row_to_dict(row: FinancialData) -> dict:
    return {
        "company_id": row.company_id,
        "period": row.period,
        "reprt_code": row.reprt_code,
        "fs_div": row.fs_div,
        "source": row.source,
        "metrics": json.loads(row.metrics_json),
        "fetched_at": row.fetched_at,
    }


def get_stored_financials(
    session: Session,
    company_id: str,
    years: int = DEFAULT_YEARS,
) -> list[FinancialData]:
    stmt = select(FinancialData).where(FinancialData.company_id == company_id)
    rows = list(session.exec(stmt).all())
    rows.sort(key=lambda r: period_sort_key(r.period), reverse=True)
    limit = max(1, min(years * 2, 16))
    return rows[:limit]


def get_annual_financials(
    session: Session,
    company_id: str,
    years: int = DEFAULT_YEARS,
) -> list[FinancialData]:
    stmt = (
        select(FinancialData)
        .where(FinancialData.company_id == company_id)
        .where(FinancialData.reprt_code == "11011")
    )
    rows = list(session.exec(stmt).all())
    # period가 YYYY 인 것만 (분기 라벨 제외)
    rows = [r for r in rows if is_annual_period(r.period)]
    rows.sort(key=lambda r: period_sort_key(r.period), reverse=True)
    return rows[: max(1, min(years, 10))]


def upsert_financial(
    session: Session,
    *,
    company_id: str,
    period: str,
    metrics: dict,
    source: str,
    reprt_code: str,
    fs_div: str,
) -> FinancialData:
    stmt = (
        select(FinancialData)
        .where(FinancialData.company_id == company_id)
        .where(FinancialData.period == period)
        .where(FinancialData.reprt_code == reprt_code)
        .where(FinancialData.fs_div == fs_div)
    )
    row = session.exec(stmt).first()
    if row is None:
        row = FinancialData(
            company_id=company_id,
            period=period,
            reprt_code=reprt_code,
            fs_div=fs_div,
            source=source,
            metrics_json=_metrics_to_json(metrics),
            fetched_at=datetime.utcnow(),
        )
        session.add(row)
    else:
        row.source = source
        row.metrics_json = _metrics_to_json(metrics)
        row.fetched_at = datetime.utcnow()
    session.commit()
    session.refresh(row)
    return row


def load_seed_for_company(session: Session, company_id: str) -> int:
    if not SEED_PATH.exists():
        return 0
    with SEED_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    periods = payload.get(company_id) or []
    n = 0
    for item in periods:
        upsert_financial(
            session,
            company_id=company_id,
            period=str(item["period"]),
            metrics=item["metrics"],
            source="seed",
            reprt_code="11011",
            fs_div="CFS",
        )
        n += 1
    return n


def _fetch_metrics(
    client: DartClient,
    corp_code: str,
    year: int,
    reprt_code: str,
    prefer_fs: str | None = None,
) -> tuple[dict, str]:
    """prefer_fs 우선, 실패 시 다른 유형. (metrics, fs_div) 반환."""
    order = ["CFS", "OFS"]
    if prefer_fs == "OFS":
        order = ["OFS", "CFS"]
    elif prefer_fs == "CFS":
        order = ["CFS", "OFS"]

    last_error: DartApiError | None = None
    for fs_div in order:
        try:
            rows = client.fetch_statements(
                corp_code,
                str(year),
                reprt_code=reprt_code,
                fs_div=fs_div,
            )
            metrics = extract_metrics_from_dart_rows(rows)
            if metrics.get("revenue") is not None or metrics.get("total_assets") is not None:
                metrics["fs_div_used"] = fs_div
                return metrics, fs_div
        except DartApiError as exc:
            last_error = exc
            if exc.status != "013":
                raise
    if last_error:
        raise last_error
    raise DartApiError("013", "조회된 데이터가 없습니다.")


def is_financials_stale(rows: list[FinancialData]) -> bool:
    """연간 데이터가 없거나 너무 오래되면 stale."""
    if not rows:
        return True
    if all((r.source or "") == "seed" for r in rows):
        return True
    annual = [r for r in rows if is_annual_period(r.period) and r.reprt_code == "11011"]
    if not annual:
        # 분기만 있으면 연간 확보를 위해 재동기화
        return True
    latest_annual = max(period_sort_key(r.period) for r in annual)
    expected = (datetime.utcnow().year - 1, 4)
    return latest_annual < expected


def sync_from_dart(
    session: Session,
    company: Company,
    years: int = DEFAULT_YEARS,
) -> tuple[int, list[str]]:
    """
    1) 연간 보고서 우선 수집 (CFS→OFS)
    2) 최신 분기 스냅샷 추가
    """
    client = DartClient()
    if not client.has_key:
        raise DartApiError("NO_KEY", "DART_API_KEY가 설정되지 않았습니다.")

    messages: list[str] = []
    ok = 0
    current_year = datetime.utcnow().year
    prefer_fs: str | None = None

    # 1) 연간: 전년도부터 years개 (동일 fs_div 유지)
    for year in range(current_year - 1, current_year - years - 1, -1):
        label = str(year)
        try:
            metrics, fs_div = _fetch_metrics(
                client, company.corp_code, year, "11011", prefer_fs=prefer_fs
            )
            if prefer_fs is None:
                prefer_fs = fs_div
            metrics["report_type"] = "FY"
            upsert_financial(
                session,
                company_id=company.company_id,
                period=label,
                metrics=metrics,
                source="dart",
                reprt_code="11011",
                fs_div=fs_div,
            )
            ok += 1
        except DartApiError as exc:
            if exc.status == "013":
                messages.append(f"{label} 연간: 데이터 없음")
            else:
                messages.append(f"{label} 연간: {exc}")
                if exc.status == "020":
                    return ok, messages
        except Exception as exc:  # noqa: BLE001
            logger.exception("DART 연간 sync 실패 %s %s", company.company_id, label)
            messages.append(f"{label} 연간: {exc}")

    # 당해 연간(있으면)
    try:
        metrics, fs_div = _fetch_metrics(
            client, company.corp_code, current_year, "11011", prefer_fs=prefer_fs
        )
        if prefer_fs is None:
            prefer_fs = fs_div
        metrics["report_type"] = "FY"
        upsert_financial(
            session,
            company_id=company.company_id,
            period=str(current_year),
            metrics=metrics,
            source="dart",
            reprt_code="11011",
            fs_div=fs_div,
        )
        ok += 1
    except DartApiError as exc:
        if exc.status not in {"013"}:
            messages.append(f"{current_year} 연간: {exc}")
            if exc.status == "020":
                return ok, messages

    # 2) 최신 분기 스냅샷 (연간과 같은 fs_div 우선)
    interim_ok = 0
    for year in (current_year, current_year - 1):
        for reprt_code, suffix in INTERIM_SPECS:
            if interim_ok >= 3:
                break
            label = period_label(year, suffix)
            try:
                metrics, fs_div = _fetch_metrics(
                    client,
                    company.corp_code,
                    year,
                    reprt_code,
                    prefer_fs=prefer_fs,
                )
                metrics["report_type"] = suffix
                upsert_financial(
                    session,
                    company_id=company.company_id,
                    period=label,
                    metrics=metrics,
                    source="dart",
                    reprt_code=reprt_code,
                    fs_div=fs_div,
                )
                ok += 1
                interim_ok += 1
            except DartApiError as exc:
                if exc.status == "013":
                    continue
                messages.append(f"{label}: {exc}")
                if exc.status == "020":
                    return ok, messages
            except Exception as exc:  # noqa: BLE001
                logger.exception("DART 분기 sync 실패 %s %s", company.company_id, label)
                messages.append(f"{label}: {exc}")
        if interim_ok >= 3:
            break

    return ok, messages


def get_or_load_financials(
    session: Session,
    company_id: str,
    years: int = DEFAULT_YEARS,
    force_sync: bool = False,
) -> tuple[list[dict], str | None]:
    """저장된 재무 반환. 필요 시 DART 재동기화(연간 우선 + 최신 분기)."""
    company = session.get(Company, company_id)
    if company is None:
        raise LookupError("기업을 찾을 수 없습니다.")

    client = DartClient()
    note = None
    rows = get_stored_financials(session, company_id, years=years)
    should_sync = force_sync or (client.has_key and is_financials_stale(rows))

    if should_sync and client.has_key:
        ok, messages = sync_from_dart(session, company, years=years)
        missing = [m for m in messages if "데이터 없음" in m]
        hard = [m for m in messages if "데이터 없음" not in m]
        if ok == 0 and not rows:
            note = "DART 조회 결과가 없어 seed를 시도합니다. " + "; ".join(messages[:3])
            load_seed_for_company(session, company_id)
        elif ok == 0 and rows:
            note = "DART 최신 동기화 실패 - 기존 데이터를 사용합니다. " + "; ".join(hard[:3] or messages[:3])
        elif hard:
            note = "; ".join(hard[:3])
        elif missing and ok < 2:
            note = "일부 기간 공시가 없어 확보된 기간만 표시합니다."
        rows = get_stored_financials(session, company_id, years=years)
    elif should_sync and not client.has_key:
        if not rows:
            n = load_seed_for_company(session, company_id)
            note = (
                "DART_API_KEY가 없고 해당 기업 seed 재무도 없습니다."
                if n == 0
                else "DART_API_KEY 미설정 - seed 재무 데이터를 사용합니다."
            )
            rows = get_stored_financials(session, company_id, years=years)
        else:
            note = "DART_API_KEY 미설정 - 저장된 재무 데이터를 사용합니다."
    elif not rows:
        if client.has_key:
            ok, messages = sync_from_dart(session, company, years=years)
            if ok == 0:
                note = "DART 조회 결과가 없어 seed를 시도합니다. " + "; ".join(messages[:3])
                load_seed_for_company(session, company_id)
            elif messages:
                note = "; ".join(messages[:3])
        else:
            n = load_seed_for_company(session, company_id)
            note = (
                "DART_API_KEY가 없고 해당 기업 seed 재무도 없습니다."
                if n == 0
                else "DART_API_KEY 미설정 - seed 재무 데이터를 사용합니다."
            )
        rows = get_stored_financials(session, company_id, years=years)

    return [_row_to_dict(r) for r in rows], note


def _preferred_fs_div(rows: list[dict]) -> str:
    """다수 공시 유형. 동점이면 CFS 우선."""
    if not rows:
        return "CFS"
    counts: dict[str, int] = {}
    for r in rows:
        fs = str(r.get("fs_div") or "CFS")
        counts[fs] = counts.get(fs, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], 0 if x[0] == "CFS" else 1))[0][0]


def split_latest_and_annual(
    items: list[dict],
) -> tuple[list[dict], list[dict], list[dict], str]:
    """전체 / 연간 추세 / 분기 추세 분리. 동일 fs_div로 맞춤. (…, preferred_fs)"""
    preferred = _preferred_fs_div(items)
    same_fs = [i for i in items if str(i.get("fs_div") or "CFS") == preferred]
    items_sorted = sorted(
        same_fs, key=lambda i: period_sort_key(str(i.get("period"))), reverse=True
    )

    annual = [
        i
        for i in same_fs
        if is_annual_period(str(i.get("period") or "")) and i.get("reprt_code") == "11011"
    ]
    if not annual:
        annual = [i for i in same_fs if is_annual_period(str(i.get("period") or ""))]
    annual.sort(key=lambda i: period_sort_key(str(i.get("period"))), reverse=True)

    interim = [
        i
        for i in same_fs
        if not is_annual_period(str(i.get("period") or ""))
        and str(i.get("reprt_code") or "") in {"11013", "11012", "11014"}
    ]
    if not interim:
        interim = [
            i for i in same_fs if not is_annual_period(str(i.get("period") or ""))
        ]
    interim.sort(key=lambda i: period_sort_key(str(i.get("period"))), reverse=True)

    return items_sorted, annual, interim, preferred
