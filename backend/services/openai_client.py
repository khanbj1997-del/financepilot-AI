"""OpenAI Chat Completions 클라이언트 (requests 기반)."""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class OpenAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = (api_key if api_key is not None else settings.openai_api_key or "").strip()
        self.model = model or getattr(settings, "openai_model", None) or DEFAULT_MODEL
        self.timeout = timeout

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.has_key:
            raise OpenAIError("OPENAI_API_KEY가 설정되지 않았습니다.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            res = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise OpenAIError(f"OpenAI 요청 실패: {exc}") from exc

        if res.status_code >= 400:
            raise OpenAIError(
                f"OpenAI HTTP {res.status_code}: {res.text[:300]}",
                status_code=res.status_code,
            )

        data = res.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAIError(f"OpenAI 응답 형식 오류: {data}") from exc

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenAIError(f"JSON 파싱 실패: {content[:300]}") from exc
