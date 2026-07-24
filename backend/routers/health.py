"""헬스체크 라우터."""
from fastapi import APIRouter

from config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """서버 상태 + 분석 설정 요약(키 값은 노출하지 않음)."""
    return {
        "status": "ok",
        "analysis_provider": settings.analysis_provider,
        "groq_key_set": bool(settings.groq_api_key),
        "dart_key_set": bool(settings.dart_api_key),
        "groq_model": settings.groq_model,
    }
