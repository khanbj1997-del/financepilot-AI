"""SQLite 엔진 및 세션 헬퍼."""
from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

_COMPANY_EXTRA_COLUMNS = (
    ("industry_source", "VARCHAR(20)"),
    ("industry_confidence", "FLOAT"),
    ("industry_updated_at", "VARCHAR(32)"),
)


def _migrate_company_columns() -> None:
    """기존 SQLite company 테이블에 업종 메타 컬럼이 없으면 추가."""
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(company)")).fetchall()
        if not rows:
            return
        existing = {r[1] for r in rows}
        for name, col_type in _COMPANY_EXTRA_COLUMNS:
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE company ADD COLUMN {name} {col_type}"))


def init_db() -> None:
    """정의된 SQLModel 테이블을 생성한다."""
    SQLModel.metadata.create_all(engine)
    _migrate_company_columns()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
