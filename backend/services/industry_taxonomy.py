"""업종 분류 체계·미분류 판별·KSIC(업종코드) 매핑."""
from __future__ import annotations

from typing import Any

# industry_profiles.json 키와 맞추고, 확장 분류는 프로필 없으면 default로 해석
ALLOWED_INDUSTRIES: tuple[str, ...] = (
    "반도체",
    "전자·전기",
    "자동차",
    "2차전지",
    "배터리",
    "화학",
    "철강",
    "철강·금속",
    "건설",
    "조선·기계",
    "바이오",
    "바이오·제약",
    "의료기기",
    "금융",
    "보험",
    "증권",
    "유통",
    "식품",
    "통신",
    "소프트웨어·IT",
    "인터넷서비스",
    "게임",
    "미디어·엔터테인먼트",
    "에너지",
    "유틸리티",
    "운송·물류",
    "부동산",
    "소비재",
    "기타",
)

# 프로필 JSON 키가 다른 경우 별칭
PROFILE_KEY_ALIASES: dict[str, str] = {
    "2차전지": "배터리",
    "철강·금속": "철강",
    "바이오·제약": "바이오",
    "소프트웨어·IT": "인터넷서비스",
    "전자·전기": "반도체",
}

# '기타'는 허용 업종(추정 결과)으로 취급한다. 재호출 트리거는 '미분류' 등만.
UNCLASSIFIED_VALUES = frozenset({"", "미분류", "일반", "unknown", "n/a", "na", "none"})

# DART induty_code(한국표준산업분류 계열) → 허용 업종
# 코드는 자릿수가 2~3인 경우가 많음. 긴 prefix 우선 매칭.
_KSIC_PREFIX_MAP: list[tuple[str, str]] = [
    ("264", "반도체"),  # 전자부품 중 반도체 관련(삼성전자 등)
    ("261", "반도체"),
    ("262", "전자·전기"),
    ("263", "전자·전기"),
    ("265", "전자·전기"),
    ("266", "전자·전기"),
    ("26", "전자·전기"),
    ("29", "자동차"),
    ("30", "조선·기계"),
    ("28", "전자·전기"),
    ("27", "의료기기"),
    ("21", "바이오·제약"),
    ("20", "화학"),
    ("22", "화학"),
    ("24", "철강·금속"),
    ("25", "철강·금속"),
    ("41", "건설"),
    ("42", "건설"),
    ("35", "유틸리티"),
    ("06", "에너지"),
    ("05", "에너지"),
    ("19", "에너지"),
    ("58", "소프트웨어·IT"),
    ("59", "미디어·엔터테인먼트"),
    ("60", "미디어·엔터테인먼트"),
    ("61", "통신"),
    ("62", "소프트웨어·IT"),
    ("63", "소프트웨어·IT"),
    ("64", "금융"),
    ("65", "보험"),
    ("66", "증권"),
    ("45", "유통"),
    ("46", "유통"),
    ("47", "유통"),
    ("10", "식품"),
    ("11", "식품"),
    ("12", "식품"),
    ("49", "운송·물류"),
    ("50", "운송·물류"),
    ("51", "운송·물류"),
    ("52", "운송·물류"),
    ("68", "부동산"),
    ("55", "소비재"),
    ("56", "소비재"),
]


def is_unclassified(industry: str | None) -> bool:
    if industry is None:
        return True
    text = str(industry).strip()
    if not text:
        return True
    return text.lower() in UNCLASSIFIED_VALUES or text in UNCLASSIFIED_VALUES


def normalize_industry(name: str | None) -> str | None:
    """허용 목록에 맞게 정규화. 불가하면 None."""
    if not name or is_unclassified(name):
        return None
    text = str(name).strip()
    if text in ALLOWED_INDUSTRIES:
        return text
    # 공백·중점 변형
    compact = text.replace(" ", "").replace("·", "").replace("-", "")
    for allowed in ALLOWED_INDUSTRIES:
        if allowed.replace(" ", "").replace("·", "").replace("-", "") == compact:
            return allowed
    return None


def profile_key_for(industry: str | None) -> str:
    """industry_profiles.json 조회용 키."""
    if not industry or is_unclassified(industry):
        return "default"
    if industry in PROFILE_KEY_ALIASES:
        return PROFILE_KEY_ALIASES[industry]
    return industry


def map_induty_code(induty_code: str | None) -> str | None:
    """DART 업종코드 → 허용 업종명."""
    code = (induty_code or "").strip()
    if not code:
        return None
    for prefix, industry in _KSIC_PREFIX_MAP:
        if code.startswith(prefix):
            return industry
    return None


def allowed_industries_for_prompt() -> list[str]:
    return list(ALLOWED_INDUSTRIES)
