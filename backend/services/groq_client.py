"""Groq Chat Completions 클라이언트 (OpenAI 호환, requests 기반)."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from config import settings

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class GroqClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 90):
        self.api_key = (api_key if api_key is not None else settings.groq_api_key or "").strip()
        self.model = model or settings.groq_model or DEFAULT_MODEL
        self.timeout = timeout

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.has_key:
            raise GroqError("GROQ_API_KEY가 설정되지 않았습니다.")

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

        last_error: GroqError | None = None
        for attempt in range(3):
            try:
                res = requests.post(
                    GROQ_URL, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.RequestException as exc:
                raise GroqError(f"Groq 요청 실패: {exc}") from exc

            if res.status_code in {429, 502, 503}:
                last_error = GroqError(
                    f"Groq HTTP {res.status_code}: {res.text[:300]}",
                    status_code=res.status_code,
                )
                # 짧은 대기 후 재시도 (레이트 리밋·일시 장애)
                time.sleep(1.5 * (attempt + 1))
                continue

            if res.status_code >= 400:
                raise GroqError(
                    f"Groq HTTP {res.status_code}: {res.text[:300]}",
                    status_code=res.status_code,
                )

            data = res.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise GroqError(f"Groq 응답 형식 오류: {data}") from exc

            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise GroqError(f"JSON 파싱 실패: {content[:300]}") from exc

        assert last_error is not None
        raise last_error
