"""업종 미분류 시 Groq로 허용 목록 내 업종 추정 (캐시·중복 호출 방지)."""
from __future__ import annotations

import json
import logging
from typing import Any

from models.company import Company
from services.groq_client import GroqClient, GroqError
from services.industry_taxonomy import ALLOWED_INDUSTRIES, normalize_industry

logger = logging.getLogger(__name__)

MIN_CONFIDENCE_TO_SAVE = 0.55


def _system_prompt() -> str:
    allowed = ", ".join(ALLOWED_INDUSTRIES)
    return f"""당신은 한국 상장기업의 대표 업종을 분류하는 보조 AI다.
반드시 아래 허용 업종 목록 중 정확히 하나만 선택한다.
허용 목록: {allowed}

규칙:
1) 기업명만으로 단정하지 말고, 제공된 사업·기업 정보만 근거로 한다.
2) 없는 사실을 만들지 않는다. 정보가 부족하면 confidence를 낮게 둔다.
3) 여러 사업이 있으면 핵심(매출·본업) 기준으로 대표 업종 하나.
4) 허용 목록에 없는 새 업종명을 만들지 않는다.
5) 자연스러운 한국어 reason만 작성한다(한자·중국어 금지).

JSON만 출력:
{{"industry":"허용목록중하나","confidence":0.0,"reason":"근거 한두 문장"}}
confidence는 0~1 실수. 근거가 약하면 0.5 미만."""


def _user_prompt(company: Company, overview: dict[str, Any] | None) -> str:
    overview = overview or {}
    payload = {
        "company_name": company.company_name,
        "stock_code": company.stock_code,
        "corp_code": company.corp_code or company.company_id,
        "dart_overview": {
            "corp_name": overview.get("corp_name"),
            "stock_name": overview.get("stock_name"),
            "induty_code": overview.get("induty_code"),
            "adres": overview.get("adres"),
            "hm_url": overview.get("hm_url"),
            "corp_cls": overview.get("corp_cls"),
        },
        "note": "induty_code는 산업분류 코드일 뿐이며, 허용 업종명으로 매핑해 답한다.",
    }
    return json.dumps(payload, ensure_ascii=False)


def estimate_industry_with_groq(
    company: Company,
    overview: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    성공 시 {industry, confidence, reason, source='groq'}
    실패·낮은 신뢰도·목록 외 → None (미분류 유지)
    """
    client = GroqClient()
    if not client.has_key:
        logger.warning("업종 추정 생략: GROQ_API_KEY 없음")
        return None

    try:
        raw = client.chat_json(_system_prompt(), _user_prompt(company, overview))
    except GroqError as exc:
        logger.warning("업종 Groq 추정 실패: %s", exc)
        return None

    industry = normalize_industry(str(raw.get("industry") or ""))
    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(raw.get("reason") or "").strip()[:300]

    if industry is None:
        logger.info("업종 추정 결과가 허용 목록 밖: %s", raw.get("industry"))
        return None
    if confidence < MIN_CONFIDENCE_TO_SAVE:
        logger.info(
            "업종 추정 신뢰도 부족(%.2f) → 미분류 유지: %s",
            confidence,
            company.company_name,
        )
        return None

    return {
        "industry": industry,
        "confidence": round(confidence, 3),
        "reason": reason,
        "source": "groq",
    }
