"""금액·비율 표시용 포맷 (내부 계산값과 분리, 표시 전용)."""
from __future__ import annotations

import re
from typing import Any

# 원(KRW) 기준 단위
_UNIT_GYEONG = 1e16  # 경
_UNIT_JO = 1e12  # 조
_UNIT_EOK = 1e8  # 억
_UNIT_MAN = 1e4  # 만

_RATIO_LABELS = (
    "부채비율",
    "유동비율",
    "영업이익률",
    "매출 성장률",
    "영업이익 성장률",
    "매출성장률",
    "영업이익성장률",
    "성장률",
    "ROE",
    "ROIC",
    "roe",
    "roic",
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("%", "")
        if not text or text in {"-", "데이터 없음", "N/A", "null"}:
            return None
        # 이미 포맷된 한글 단위 문자열은 재변환하지 않음(표시 유지)
        if any(u in text for u in ("경원", "조원", "억원", "만원", "원")):
            return None
        try:
            return float(text)
        except ValueError:
            return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def _trim_decimals(num_str: str) -> str:
    """소수점 둘째 자리 반올림 결과에서 불필요한 후행 0 제거 (23.10→23.1, 23.00→23)."""
    if "." not in num_str:
        return num_str
    return num_str.rstrip("0").rstrip(".")


def _format_scaled(value: float, divisor: float, unit: str) -> str:
    scaled = round(value / divisor, 2)
    # 절댓값 기준으로 천 단위 구분, 부호는 앞에
    sign = "-" if scaled < 0 else ""
    abs_scaled = abs(scaled)
    body = f"{abs_scaled:,.2f}"
    body = _trim_decimals(body)
    return f"{sign}{body}{unit}"


def format_financial_amount(value: Any, *, empty: str = "데이터 없음") -> str:
    """
    큰 금액을 경/조/억/만 단위로 표시.
    내부 계산값을 변경하지 않으며, 표시용 문자열만 반환한다.
    """
    if isinstance(value, str):
        text = value.strip()
        if any(u in text for u in ("경원", "조원", "억원", "만원")) and re.search(r"\d", text):
            return text
        if text.endswith("원") and re.search(r"\d", text) and not re.fullmatch(r"-?\d+(\.\d+)?", text.replace(",", "")):
            return text

    n = _as_float(value)
    if n is None:
        return empty

    if n == 0:
        return "0원"

    abs_n = abs(n)
    if abs_n >= _UNIT_GYEONG:
        return _format_scaled(n, _UNIT_GYEONG, "경원")
    if abs_n >= _UNIT_JO:
        return _format_scaled(n, _UNIT_JO, "조원")
    if abs_n >= _UNIT_EOK:
        return _format_scaled(n, _UNIT_EOK, "억원")
    if abs_n >= _UNIT_MAN:
        return _format_scaled(n, _UNIT_MAN, "만원")
    # 만원 미만: 원 단위 (정수, 천 단위 구분)
    rounded = int(round(n))
    return f"{rounded:,}원"


def format_percent(value: Any, *, empty: str = "데이터 없음") -> str:
    """비율을 항상 % 포함해 표시. 이미 %가 있으면 중복하지 않음."""
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            inner = text[:-1].strip().replace(",", "")
            try:
                return f"{float(inner):.2f}%"
            except ValueError:
                return text if text else empty

    n = _as_float(value)
    if n is None:
        return empty
    return f"{n:.2f}%"


def build_display_metrics(raw: dict[str, Any] | None) -> dict[str, str | None]:
    """원본 수치 dict → 표시용 문자열 dict (계산용 raw와 분리)."""
    raw = raw or {}
    amount_keys = (
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "fcf",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "current_assets",
        "current_liabilities",
        "interest_expense",
    )
    percent_keys = (
        "roe",
        "roic",
        "operating_margin",
        "debt_ratio",
        "current_ratio",
        "revenue_growth",
        "operating_income_growth",
        "revenue_growth_yoy",
        "operating_income_growth_yoy",
    )
    out: dict[str, str | None] = {}
    for key in amount_keys:
        if key in raw:
            out[key] = format_financial_amount(raw.get(key))
    for key in percent_keys:
        if key in raw:
            out[key] = format_percent(raw.get(key))
    if "interest_coverage" in raw:
        ic = _as_float(raw.get("interest_coverage"))
        out["interest_coverage"] = f"{ic:.2f}배" if ic is not None else "데이터 없음"
    return out


def rewrite_raw_numbers_in_text(text: str, raw_metrics: dict[str, Any] | None = None) -> str:
    """
    분석 문장에 노출된 원시 큰 숫자·비율을 표시 형식으로 치환.
    내부 계산값은 바꾸지 않고 문장만 정리한다.
    """
    if not text:
        return text
    out = text
    raw_metrics = raw_metrics or {}

    # 1) 알려진 금액 메트릭 원시값 → 표시값 (긴 문자열부터)
    replacements: list[tuple[str, str]] = []
    amount_keys = (
        "fcf",
        "operating_cash_flow",
        "revenue",
        "operating_income",
        "net_income",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "current_assets",
        "current_liabilities",
    )
    for key in amount_keys:
        val = _as_float(raw_metrics.get(key))
        if val is None or abs(val) < 1e4:
            continue
        display = format_financial_amount(val)
        for candidate in _numeric_variants(val):
            if len(candidate) >= 5:
                replacements.append((candidate, display))

    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    for src, dst in replacements:
        if src and src in out:
            out = out.replace(src, dst)

    # 2) 남은 큰 원시 숫자(만원 이상) 일반 치환
    def _repl_amount(match: re.Match[str]) -> str:
        raw = match.group(1)
        try:
            n = float(raw)
        except ValueError:
            return raw
        if abs(n) < 10000:
            return raw
        return format_financial_amount(n)

    out = re.sub(r"(?<![\d.])(-?\d{5,}(?:\.\d+)?)(?!\s*%|%|[0-9]|조|억|만|경|원|배)", _repl_amount, out)

    # 3) 비율 라벨 뒤 숫자에 % 보강 (이미 %면 유지, 소수점 2자리로 정규화)
    label_alt = "|".join(re.escape(x) for x in _RATIO_LABELS)

    def _repl_ratio(match: re.Match[str]) -> str:
        label, particle, num = match.group(1), match.group(2) or "", match.group(3)
        try:
            formatted = format_percent(float(num))
        except ValueError:
            return match.group(0)
        spacer = " " if particle and not particle.startswith(" ") else ""
        if particle and not particle.startswith(" ") and not particle.startswith("\n"):
            return f"{label}{particle} {formatted}"
        return f"{label}{particle}{spacer}{formatted}"

    out = re.sub(
        rf"({label_alt})(\s*(?:은|는|이|가))?\s*(-?\d+(?:\.\d+)?)(?![\d.])(?!\s*%|%)",
        _repl_ratio,
        out,
    )

    # 4) 알려진 비율값(소수점 2자리 정확 일치)만 단독 숫자→% (부분 매칭 방지)
    percent_keys = (
        "current_ratio",
        "debt_ratio",
        "operating_margin",
        "roe",
        "roic",
        "revenue_growth",
        "operating_income_growth",
    )
    for key in percent_keys:
        val = _as_float(raw_metrics.get(key))
        if val is None:
            continue
        display = format_percent(val)
        cand = f"{val:.2f}"
        out = re.sub(
            rf"(?<![\d.]){re.escape(cand)}(?!\d)(?!\s*%|%)",
            display,
            out,
        )

    out = out.replace("%%", "%")
    return out


def _numeric_variants(value: float, *, include_int: bool = False) -> list[str]:
    """치환용 숫자 문자열 후보."""
    variants = {
        str(value),
        f"{value:.1f}",
        f"{value:.2f}",
        f"{value:.0f}",
        f"{value:.10g}",
    }
    if include_int or abs(value - round(value)) < 1e-9:
        variants.add(str(int(round(value))))
    # 과학적 표기 제거된 정수형 큰 수
    if abs(value) >= 1:
        variants.add(f"{value:.0f}")
        variants.add(str(int(value)) if value == int(value) else str(value))
    return [v for v in variants if v and v not in {"nan", "inf", "-inf"}]
