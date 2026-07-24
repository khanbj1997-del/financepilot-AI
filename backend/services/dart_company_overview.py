"""DART 기업개황(company.json) 조회 — 업종코드(induty_code) 포함."""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"


class DartCompanyInfoError(Exception):
    pass


def fetch_company_overview(corp_code: str, timeout: int = 20) -> dict[str, Any]:
    """
    DART 기업개황.
    응답 예: induty_code, corp_name, stock_code, adres, ...
    corpCode.xml에는 업종이 없고, 이 API에만 induty_code가 있다.
    """
    key = (settings.dart_api_key or "").strip()
    if not key:
        raise DartCompanyInfoError("DART_API_KEY가 설정되지 않았습니다.")
    code = (corp_code or "").strip()
    if not code:
        raise DartCompanyInfoError("corp_code가 없습니다.")

    try:
        res = requests.get(
            COMPANY_URL,
            params={"crtfc_key": key, "corp_code": code},
            timeout=timeout,
        )
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError) as exc:
        raise DartCompanyInfoError(f"기업개황 요청 실패: {exc}") from exc

    status = str(data.get("status") or "")
    if status != "000":
        raise DartCompanyInfoError(
            f"DART 기업개황 오류 [{status}]: {data.get('message')}"
        )
    return data
