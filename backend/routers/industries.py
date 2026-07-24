"""업종 프로필 API."""
from fastapi import APIRouter, HTTPException

from schemas.industry import IndustryListResponse, IndustryProfileOut
from services import industry_profile as ip

router = APIRouter(prefix="/industries", tags=["industries"])


@router.get("", response_model=IndustryListResponse)
def list_industries():
    items = ip.list_industries()
    return IndustryListResponse(total=len(items), items=items)


@router.get("/{industry_name}", response_model=IndustryProfileOut)
def get_industry_profile(industry_name: str):
    profile = ip.get_profile(industry_name)
    if not profile.get("matched") and industry_name.strip() not in ("default", "일반"):
        # 미매칭이어도 default 프로필 반환 (404 대신 안내)
        pass
    return IndustryProfileOut(**profile)
