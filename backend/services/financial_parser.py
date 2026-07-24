"""DART 계정과목 목록 → 내부 metrics dict 정제."""
from __future__ import annotations

from typing import Any


def parse_amount(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—"}:
        return None
    text = text.replace(",", "").replace(" ", "")
    try:
        return int(float(text))
    except ValueError:
        return None


# (결과 키, 계정명 후보, account_id 후보)
_ACCOUNT_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "revenue",
        ("매출액", "수익(매출액)", "영업수익"),
        ("ifrs-full_Revenue",),
    ),
    (
        "operating_income",
        ("영업이익(손실)", "영업이익", "영업손실"),
        ("dart_OperatingIncomeLoss", "ifrs-full_OperatingIncome"),
    ),
    (
        "net_income",
        ("당기순이익(손실)", "당기순이익", "당기순손익"),
        ("ifrs-full_ProfitLoss",),
    ),
    (
        "operating_cash_flow",
        ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로 인한 현금흐름"),
        ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
    ),
    ("total_assets", ("자산총계",), ("ifrs-full_Assets",)),
    ("total_liabilities", ("부채총계",), ("ifrs-full_Liabilities",)),
    ("total_equity", ("자본총계",), ("ifrs-full_Equity",)),
    ("current_assets", ("유동자산",), ("ifrs-full_CurrentAssets",)),
    ("current_liabilities", ("유동부채",), ("ifrs-full_CurrentLiabilities",)),
    (
        "interest_expense",
        ("이자비용", "금융비용", "이자비용(금융비용)"),
        ("ifrs-full_FinanceCosts", "ifrs-full_InterestExpense"),
    ),
]

_PNL_SJ = {"IS", "CIS"}


def _normalize_name(name: str) -> str:
    # 로마숫자·기호 제거 후 비교
    cleaned = (
        name.replace(" ", "")
        .replace("\u3000", "")
        .replace("Ⅰ", "")
        .replace("Ⅱ", "")
        .replace("Ⅲ", "")
        .replace("Ⅳ", "")
        .replace("Ⅴ", "")
        .replace("Ⅵ", "")
        .replace("Ⅶ", "")
        .replace("Ⅷ", "")
        .replace("Ⅸ", "")
        .replace("Ⅹ", "")
        .replace(".", "")
    )
    return cleaned


def _pick_amount(
    rows: list[dict[str, Any]],
    name_candidates: tuple[str, ...],
    id_candidates: tuple[str, ...],
    *,
    prefer_pnl: bool,
) -> int | None:
    # 1) account_id 정확 매칭 (PNL 우선)
    id_set = set(id_candidates)
    if id_set:
        ranked = sorted(
            rows,
            key=lambda r: (
                0 if (r.get("sj_div") or "") in _PNL_SJ else 1,
                0 if prefer_pnl else 0,
            ),
        )
        for row in ranked:
            aid = str(row.get("account_id") or "")
            if aid in id_set:
                amount = parse_amount(row.get("thstrm_amount"))
                if amount is not None:
                    return amount

    # 2) 계정명 매칭
    norm_cands = [_normalize_name(c) for c in name_candidates]
    best: tuple[int, int] | None = None  # (score, amount) lower score better
    for row in rows:
        sj = str(row.get("sj_div") or "")
        if prefer_pnl and sj not in _PNL_SJ and sj not in {"", "IS", "CIS"}:
            # CF/BS 등은 영업이익 매칭에서 제외
            if prefer_pnl:
                continue
        name = _normalize_name(str(row.get("account_nm") or ""))
        if not name:
            continue
        amount = parse_amount(row.get("thstrm_amount"))
        if amount is None:
            continue
        for cand in norm_cands:
            if not cand:
                continue
            if name == cand:
                score = 0
            elif name.endswith(cand) or cand in name:
                # '영업손실' ↔ '영업이익' 계열
                score = 1
            else:
                continue
            if sj in _PNL_SJ:
                score -= 10
            if best is None or score < best[0]:
                best = (score, amount)
            break
    return best[1] if best else None


def extract_metrics_from_dart_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    fnlttSinglAcntAll list 항목에서 핵심 금액을 뽑는다.
    당기(thstrm_amount) 우선. 손익 항목은 IS/CIS 우선.
    """
    metrics: dict[str, Any] = {}
    for key, names, ids in _ACCOUNT_RULES:
        prefer_pnl = key in {
            "revenue",
            "operating_income",
            "net_income",
            "interest_expense",
        }
        amount = _pick_amount(rows, names, ids, prefer_pnl=prefer_pnl)
        if amount is not None:
            metrics[key] = amount

    # 영업손실만 있고 영업이익 키가 비면 이미 operating_income에 손실 금액이 들어감
    ocf = metrics.get("operating_cash_flow")
    capex = None
    for row in rows:
        name = _normalize_name(str(row.get("account_nm") or ""))
        if "유형자산의취득" in name or name.endswith("유형자산취득"):
            amount = parse_amount(row.get("thstrm_amount"))
            if amount is not None:
                capex = abs(amount)
                break
    if ocf is not None and capex is not None:
        metrics["capex"] = capex
        metrics["fcf"] = ocf - capex
    elif ocf is not None:
        metrics["fcf"] = ocf

    metrics["currency"] = "KRW"
    metrics["unit"] = "원"
    return metrics
