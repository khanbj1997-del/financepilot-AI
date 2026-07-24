"""환경변수 로드 및 설정."""
from pathlib import Path

from dotenv import load_dotenv
import os

_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _clean_env(name: str, default: str = "") -> str:
    """환경변수 읽기. 양끝 공백·따옴표 제거 (Render 붙여넣기 실수 방지)."""
    value = (os.getenv(name) or default).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def reload_env() -> None:
    """
    backend/.env 를 로드한다.
    override=False: 이미 설정된 OS/Render Environment 값이 우선한다.
    (로컬 .env는 없는 키만 채움)
    """
    load_dotenv(_ENV_PATH, override=False)


reload_env()


class Settings:
    """os.getenv를 속성 접근 시마다 읽어 .env 변경에 덜 취약하게 한다."""

    @property
    def dart_api_key(self) -> str:
        return _clean_env("DART_API_KEY")

    @property
    def openai_api_key(self) -> str:
        return _clean_env("OPENAI_API_KEY")

    @property
    def openai_model(self) -> str:
        return _clean_env("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def gemini_api_key(self) -> str:
        return _clean_env("GEMINI_API_KEY")

    @property
    def gemini_model(self) -> str:
        return _clean_env("GEMINI_MODEL", "gemini-2.0-flash")

    @property
    def groq_api_key(self) -> str:
        return _clean_env("GROQ_API_KEY")

    @property
    def groq_model(self) -> str:
        # 70B는 무료 티어 일일 토큰(TPD)을 쉽게 소진 → 기본은 경량 모델
        return _clean_env("GROQ_MODEL", "llama-3.1-8b-instant")

    @property
    def database_url(self) -> str:
        return _clean_env("DATABASE_URL", "sqlite:///app.db")

    @property
    def analysis_provider(self) -> str:
        """
        분석 엔진 선택.
        - rule   : 로컬 규칙 기반
        - groq   : Groq API (권장 AI, 실패 시 rule 폴백)
        - gemini : Google Gemini API (유지·미사용 가능)
        - openai : OpenAI API (유지·비권장)
        """
        value = _clean_env("ANALYSIS_PROVIDER", "rule").lower()
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
