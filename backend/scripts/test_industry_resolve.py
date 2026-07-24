"""업종 해석 스모크 테스트."""
from __future__ import annotations

from database import engine, init_db
from models.company import Company
from services.company_master import get_company, restore_seed_industries
from services.dart_company_overview import fetch_company_overview
from services.industry_resolve import ensure_company_industry
from services.industry_taxonomy import is_unclassified, map_induty_code
from sqlmodel import Session, select


def main() -> None:
    init_db()
    with Session(engine) as s:
        n = restore_seed_industries(s)
        print("seed_restored", n)

        c = get_company(s, "00126380")
        print(
            "samsung_before",
            None if c is None else (c.company_name, c.industry, c.industry_source),
        )
        if c is not None and is_unclassified(c.industry):
            c.industry = "미분류"
            c.industry_source = None
            c.industry_updated_at = None
            s.add(c)
            s.commit()
            s.refresh(c)
        if c is not None:
            r = ensure_company_industry(s, c, allow_groq=True)
            s.refresh(c)
            print("samsung_resolve", r)
            print("samsung_after", c.industry, c.industry_source, c.industry_confidence)

        ov = fetch_company_overview("00126380")
        print(
            "dart_induty",
            ov.get("induty_code"),
            "mapped",
            map_induty_code(ov.get("induty_code")),
        )

        # 캐시: 두 번째 호출은 keep_existing
        if c is not None:
            r2 = ensure_company_industry(s, c, allow_groq=True)
            print("samsung_second", r2.get("action"))

        # seed 외 미분류 1건 (가능하면 Groq)
        rows = list(
            s.exec(select(Company).where(Company.industry == "미분류").limit(3)).all()
        )
        # industry null도
        if not rows:
            rows = list(
                s.exec(
                    select(Company)
                    .where(Company.industry.is_(None))  # type: ignore[union-attr]
                    .limit(3)
                ).all()
            )
        print(
            "unclassified_sample",
            [(r.company_name, r.corp_code, r.industry, r.industry_source) for r in rows],
        )
        for t in rows[:2]:
            t.industry = "미분류"
            t.industry_source = None
            t.industry_updated_at = None
            s.add(t)
            s.commit()
            s.refresh(t)
            r3 = ensure_company_industry(s, t, allow_groq=True)
            s.refresh(t)
            print("sample_resolve", t.company_name, r3)
            # 중복 호출 방지
            r4 = ensure_company_industry(s, t, allow_groq=True)
            print("sample_second", t.company_name, r4.get("action"))


if __name__ == "__main__":
    main()
