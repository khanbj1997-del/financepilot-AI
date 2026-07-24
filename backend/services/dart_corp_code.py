"""DART 고유번호(corpCode) ZIP 다운로드·파싱."""
from __future__ import annotations

import io
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"


class DartCorpCodeError(Exception):
    """DART corp_code 수집 실패."""


def fetch_listed_companies_from_dart(timeout: int = 60) -> list[dict[str, Any]]:
    """
    DART corpCode.xml(ZIP)을 받아 상장사(종목코드 있는 기업)만 반환한다.
    키가 없거나 실패하면 DartCorpCodeError.
    """
    key = (settings.dart_api_key or "").strip()
    if not key:
        raise DartCorpCodeError("DART_API_KEY가 설정되지 않았습니다.")

    try:
        res = requests.get(CORP_CODE_URL, params={"crtfc_key": key}, timeout=timeout)
        res.raise_for_status()
    except requests.RequestException as exc:
        raise DartCorpCodeError(f"DART corpCode 요청 실패: {exc}") from exc

    # 오류 시 JSON/XML 텍스트가 올 수 있음
    content_type = (res.headers.get("Content-Type") or "").lower()
    if "json" in content_type or res.content[:1] == b"{":
        raise DartCorpCodeError(f"DART 응답 오류: {res.text[:300]}")

    try:
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = zf.namelist()
            xml_name = next((n for n in names if n.lower().endswith(".xml")), None)
            if not xml_name:
                raise DartCorpCodeError("ZIP 안에 XML이 없습니다.")
            xml_bytes = zf.read(xml_name)
    except zipfile.BadZipFile as exc:
        raise DartCorpCodeError("ZIP이 아닌 응답입니다. API 키를 확인하세요.") from exc

    return _parse_corp_code_xml(xml_bytes)


def _parse_corp_code_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    text = xml_bytes.decode("utf-8")
    root = ET.fromstring(text)
    companies: list[dict[str, Any]] = []

    for node in root.iter("list"):
        corp_code = (node.findtext("corp_code") or "").strip()
        corp_name = (node.findtext("corp_name") or "").strip()
        stock_code = (node.findtext("stock_code") or "").strip()
        modify_date = (node.findtext("modify_date") or "").strip()
        if not corp_code or not corp_name:
            continue
        if not stock_code:
            continue  # MVP: 상장사만
        # corpCode.xml에는 업종 필드가 없다. 미분류를 넣지 않아
        # seed/DART 기업개황으로 이미 채운 industry를 덮어쓰지 않는다.
        companies.append(
            {
                "corp_code": corp_code,
                "company_name": corp_name,
                "stock_code": stock_code.zfill(6) if stock_code.isdigit() else stock_code,
                "modify_date": modify_date,
            }
        )

    logger.info("DART corp_code 상장사 %s건 파싱 완료", len(companies))
    return companies
