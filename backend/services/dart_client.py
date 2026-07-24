"""DART Open API 공통 클라이언트."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://opendart.fss.or.kr/api"

# DART status 코드 (공식 메시지 기준)
STATUS_OK = "000"
STATUS_NO_DATA = "013"
STATUS_RATE_LIMIT = "020"


class DartApiError(Exception):
    def __init__(self, status: str, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


class DartClient:
    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = (api_key if api_key is not None else settings.dart_api_key or "").strip()
        self.timeout = timeout
        self._last_call_at = 0.0
        self._min_interval = 0.15  # 초당 과도한 호출 완화

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_at = time.monotonic()

    def get_json(self, path: str, params: dict[str, Any], retries: int = 2) -> dict[str, Any]:
        if not self.has_key:
            raise DartApiError("NO_KEY", "DART_API_KEY가 설정되지 않았습니다.")

        payload = {"crtfc_key": self.api_key, **params}
        url = f"{BASE_URL}/{path.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            self._throttle()
            try:
                res = requests.get(url, params=payload, timeout=self.timeout)
                res.raise_for_status()
                data = res.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning("DART 요청 실패(%s/%s): %s", attempt + 1, retries + 1, exc)
                time.sleep(0.5 * (attempt + 1))
                continue

            status = str(data.get("status", ""))
            message = str(data.get("message", ""))
            if status == STATUS_OK:
                return data
            if status == STATUS_NO_DATA:
                raise DartApiError(status, message or "조회된 데이터가 없습니다.")
            if status == STATUS_RATE_LIMIT:
                last_error = DartApiError(status, message or "요청 한도 초과")
                time.sleep(1.0 * (attempt + 1))
                continue
            raise DartApiError(status, message or "DART API 오류")

        if isinstance(last_error, DartApiError):
            raise last_error
        raise DartApiError("REQUEST", f"DART 요청 실패: {last_error}")

    def fetch_statements(
        self,
        corp_code: str,
        bsns_year: str,
        reprt_code: str = "11011",
        fs_div: str = "CFS",
    ) -> list[dict[str, Any]]:
        """단일회사 전체 재무제표 (연간/분기 보고서)."""
        data = self.get_json(
            "fnlttSinglAcntAll.json",
            {
                "corp_code": corp_code,
                "bsns_year": bsns_year,
                "reprt_code": reprt_code,
                "fs_div": fs_div,
            },
        )
        return list(data.get("list") or [])

    def fetch_annual_statements(
        self,
        corp_code: str,
        bsns_year: str,
        fs_div: str = "CFS",
    ) -> list[dict[str, Any]]:
        """하위 호환: 사업보고서(연간)."""
        return self.fetch_statements(corp_code, bsns_year, reprt_code="11011", fs_div=fs_div)
