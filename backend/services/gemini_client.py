"""Google Gemini generateContent 클라이언트 (requests 기반)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = (api_key if api_key is not None else settings.gemini_api_key or "").strip()
        self.model = model or settings.gemini_model or DEFAULT_MODEL
        self.timeout = timeout

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.has_key:
            raise GeminiError("GEMINI_API_KEY가 설정되지 않았습니다.")

        url = f"{GEMINI_BASE}/{self.model}:generateContent"
        params = {"key": self.api_key}
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        try:
            res = requests.post(
                url,
                params=params,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GeminiError(f"Gemini 요청 실패: {exc}") from exc

        if res.status_code >= 400:
            raise GeminiError(
                f"Gemini HTTP {res.status_code}: {res.text[:300]}",
                status_code=res.status_code,
            )

        data = res.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            content = "".join(str(p.get("text") or "") for p in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiError(f"Gemini 응답 형식 오류: {data}") from exc

        if not content:
            raise GeminiError(f"Gemini 빈 응답: {data}")

        try:
            return _parse_json_content(content)
        except json.JSONDecodeError as exc:
            raise GeminiError(f"JSON 파싱 실패: {content[:300]}") from exc


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)
