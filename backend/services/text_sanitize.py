"""분석 결과 한국어 품질 검증·치환."""
from __future__ import annotations

import re

# 긴 구문 우선
_PHRASE_REPLACEMENTS: list[tuple[str, str]] = [
    ("良好的", "양호한"),
    ("良好", "양호"),
    ("優秀", "우수"),
    ("持續性", "지속성"),
    ("持續", "지속"),
    ("改善", "개선"),
    ("惡化", "악화"),
    ("穩定", "안정"),
    ("風險", "위험"),
    ("增長", "성장"),
    ("下降", "하락"),
    ("提升", "상승"),
    ("較高", "높은 편"),
    ("較低", "낮은 편"),
    ("顯著", "뚜렷"),
    ("需要", "필요"),
    ("能力", "능력"),
    ("效率", "효율"),
    ("資本", "자본"),
    ("現金", "현금"),
    ("流動", "유동"),
    ("負債", "부채"),
    ("營收", "매출"),
    ("營業", "영업"),
    ("利潤", "이익"),
    ("品質", "품질"),
    ("結構", "구조"),
    ("暫時", "일시"),
    ("確認", "확인"),
    ("判斷", "판단"),
]

# CJK 한자 + 히라가나/가타카나 (고유명사 예외는 최소)
_CJK_OR_KANA = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\u31f0-\u31ff]+")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def sanitize_korean_output(text: str) -> str:
    """금지 한자·중국어·일본어 표현을 한국어로 정리한다."""
    if not text:
        return text
    out = text
    for src, dst in _PHRASE_REPLACEMENTS:
        if src in out:
            out = out.replace(src, dst)
    out = _CJK_OR_KANA.sub("", out)
    out = _MULTI_SPACE.sub(" ", out)
    return out.strip()


def contains_forbidden_scripts(text: str) -> bool:
    """한자·가나 잔존 여부."""
    if not text:
        return False
    return bool(_CJK_OR_KANA.search(text))


_WEAK_CONFIRM = (
    "확인해야 합니다",
    "확인할 필요가 있습니다",
    "판단할 필요가 있습니다",
    "확인이 필요합니다",
    "확인하는 것이 중요합니다",
    "통해 확인해야",
)
_STRONG_CONCLUSION = (
    "판단됩니다",
    "동반된 것으로",
    "이어지고 있는 것으로",
    "개선된 것으로",
    "약화된 것으로",
    "긍정적입니다",
    "부정적으로",
    "제한적입니다",
    "충분합니다",
    "충분해 보입니다",
    "나타나고 있습니다",
)


def overall_lacks_conclusion(text: str) -> bool:
    """종합 판단이 '확인 필요'만으로 끝나는지 여부."""
    if not text:
        return True
    has_weak = any(w in text for w in _WEAK_CONFIRM)
    has_strong = any(s in text for s in _STRONG_CONCLUSION)
    if has_weak and not has_strong:
        return True
    # 문장 대부분이 확인 필요로만 구성
    if text.count("%") >= 3:
        return True
    if text.count("비율") >= 3:
        return True
    return False
