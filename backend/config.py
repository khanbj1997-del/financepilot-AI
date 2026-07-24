"""환경변수 로드 및 설정."""
from pathlib import Path

from dotenv import load_dotenv
import os

_ENV_PATH = Path(__file__).resolve().parent / ".env"


def reload_env() -> None:
    """backend/.env 를 다시 로드한다. (.env 수정 후에도 재시작 없이 반영)"""
    load_dotenv(_ENV_PATH, override=True)


reload_env()


class Settings:
    """os.getenv를 속성 접근 시마다 읽어 .env 변경에 덜 취약하게 한다."""

    @property
    def dart_api_key(self) -> str:
        return (os.getenv("DART_API_KEY") or "").strip()

    @property
    def openai_api_key(self) -> str:
        return (os.getenv("OPENAI_API_KEY") or "").strip()

    @property
    def openai_model(self) -> str:
        return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    @property
    def gemini_api_key(self) -> str:
        return (os.getenv("GEMINI_API_KEY") or "").strip()

    @property
    def gemini_model(self) -> str:
        return (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip()

    @property
    def groq_api_key(self) -> str:
        return (os.getenv("GROQ_API_KEY") or "").strip()

    @property
    def groq_model(self) -> str:
        return (os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()

    @property
    def database_url(self) -> str:
        return (os.getenv("DATABASE_URL") or "sqlite:///app.db").strip()

    @property
    def analysis_provider(self) -> str:
        """
        분석 엔진 선택.
        - rule   : 로컬 규칙 기반
        - groq   : Groq API (권장 AI, 실패 시 rule 폴백)
        - gemini : Google Gemini API (유지·미사용 가능)
        - openai : OpenAI API (유지·비권장)
        """
        value = (os.getenv("ANALYSIS_PROVIDER") or "rule").strip().lower()
        return value if value in {"rule", "groq", "gemini", "openai"} else "rule"

    @property
    def use_groq_analysis(self) -> bool:
        return self.analysis_provider == "groq"

    @property
    def use_gemini_analysis(self) -> bool:
        """호환용. 신규 AI 분석은 groq를 사용한다."""
        return self.analysis_provider == "gemini"

    @property
    def use_openai_analysis(self) -> bool:
        """호환용. 신규 AI 분석은 groq를 사용한다."""
        return self.analysis_provider == "openai"


settings = Settings()
