"""API 라우터 모음."""
from fastapi import APIRouter

from routers import companies, favorites, health, industries, themes

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(companies.router)
api_router.include_router(industries.router)
api_router.include_router(favorites.router)
api_router.include_router(themes.router)
