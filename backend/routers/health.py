"""헬스체크 라우터."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """서버가 살아있는지 확인. 프론트가 연결 상태를 표시할 때 사용."""
    return {"status": "ok"}
