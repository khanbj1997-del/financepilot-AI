"""
FinancePilot AI — FastAPI 엔트리포인트
======================================
실행 (conda 환경 finance):
    cd backend
    uvicorn main:app --reload
    → http://127.0.0.1:8000/health
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

import models  # noqa: F401 — SQLModel 메타데이터 등록
from database import engine, init_db
from routers import api_router
from services.company_master import ensure_company_master
from services.theme_recommend import ensure_themes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        result = ensure_company_master(session)
        logger.info("Company Master: %s", result)
        theme_result = ensure_themes(session)
        logger.info("Themes: %s", theme_result)
    yield


app = FastAPI(title="FinancePilot AI API", lifespan=lifespan)

# CORS: React(Vite) 로컬 개발 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "FinancePilot AI API. /health 또는 /docs 를 확인하세요."}


app.include_router(api_router)
