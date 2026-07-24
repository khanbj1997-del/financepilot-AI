# FinancePilot AI 개발 계획

PRD(`docs/PRD.md`)와 현재 보일러플레이트 구조를 기준으로 한다.  
프로젝트 생성·conda 환경·scaffold는 이미 완료되었으므로 **기능 구현부터** 진행한다.

---

## 현재 기준 구조

```text
financepilot/
├── backend/          # FastAPI + SQLite (SQLModel)
│   ├── main.py
│   ├── config.py     # .env 로드
│   ├── database.py
│   ├── .env / .env.example
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── routers/
│   └── requirements.txt
├── frontend/         # Vite + React + React Router
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── main.jsx
│       └── pages/    # Home / Company / Favorites
└── docs/
    ├── PRD.md
    ├── DEVELOPMENT_PLAN.md
    └── TASKS.md
```

이미 갖춰진 것: FastAPI 서버, CORS, SQLite 연결, `.env` 로드, 모듈 구조, React Router 골격, `/health` 연동.  
없는 것: 도메인 모델, DART/OpenAI 연동, 기업 분석 API·화면.

---

## 개발 원칙

1. **한 번에 하나의 기능만** 구현한다. (`docs/TASKS.md` 체크리스트 기준)
2. **백엔드 → 프론트엔드** 순서로 진행한다. (데이터·API가 먼저, 화면은 그 위)
3. 프론트엔드는 외부 공공·AI API를 **직접 호출하지 않는다**. FastAPI만 호출한다.
4. API Key는 `.env`에만 두고 코드에 하드코딩하지 않는다. (`backend/.env`)
5. MVP를 완성한 뒤에만 추가 기능(뉴스 / 추천 기업 / 즐겨찾기)에 들어간다.
6. 검색 진입과 추천 진입은 **동일한 `company_id` 기반 분석 로직**을 사용한다.

## 확정된 구현 결정

| 항목 | 결정 |
|------|------|
| 즐겨찾기 사용자 | **로그인·인증 없음**. 단일 로컬 사용자(`user_id = "local"` 고정). 회원 기능은 추가하지 않음 |
| 재무 추세 UI | **Recharts**로 간단 추세 차트 표시 (설치·사용이 단순한 표준 라이브러리) |
| 페이지 라우팅 | **React Router** 사용. 초기 경로: `/`(검색·홈), `/companies/:companyId`(분석), `/favorites`(즐겨찾기·후속) |
| 업종 참고 데이터 | **정적 JSON 파일**(또는 동등한 정적 테이블). 이후 실시간 API로 교체 가능 |
| 분석 엔진 (MVP) | **`ANALYSIS_PROVIDER=groq`** 권장 (`GROQ_API_KEY`, 실패 시 rule 폴백). Gemini/OpenAI 코드는 유지·기본 미사용. 상세: `docs/ANALYSIS_PROVIDER.md` |

---

## 전체 개발 순서 개요

```text
[Phase 0] 공통 기반 (설정·폴더 정리)     ← scaffold 제외, .env·모듈 구조만
        ↓
[Phase 1] MVP 백엔드
  1-1 Company Master / 검색
  1-2 DART 재무 수집·정제·저장
  1-3 재무지표 계산·추세
  1-4 업종 특성 참고 데이터
  1-5 종합 재무 분석 (rule / Gemini)
  1-6 기업 분석 Dashboard API
  1-7 캐시·에러 처리
        ↓
[Phase 2] MVP 프론트엔드
  2-1 검색 UI
  2-2 기업 분석 Dashboard UI
  2-3 AI 분석 결과 표시
        ↓
[Phase 3] MVP 검증·마무리
        ↓
[Phase 4] MVP 이후 — 즐겨찾기
        ↓
[Phase 5] MVP 이후 — 추천 기업 (인기 테마)
        ↓
[Phase 6] MVP 이후 — 최신 뉴스 분석
```

---

# Phase 0. 공통 기반 (최소)

scaffold는 건드리지 않고, 기능 구현에 필요한 최소 배선만 한다.

| 순서 | 작업 | 설명 |
|------|------|------|
| 0-1 | 환경변수 | `backend/.env`에 키 기입. `.env.example`로 항목 문서화 |
| 0-2 | 백엔드 모듈 구조 | `models` / `routers` / `services` / `schemas` 등으로 분리 준비 |
| 0-3 | 프론트 기반 | `api.js` 확장 + React Router 라우팅 골격 |

---

# Phase 1. MVP 백엔드 (FastAPI + DART + SQLite + OpenAI)

목표: 기업 검색 → 재무 수집·지표 계산 → AI 분석까지 **서버 API만으로** 완성.

## 1-1. Company Master & 기업 검색

```text
기업명 / 종목코드 → Company Master → company_id / corp_code
```

- `Company` 모델: `company_id`, `company_name`, `stock_code`, `corp_code`, `industry`
- DART `corp_code` 매핑 데이터 로드(서버 기동 시 또는 DB 적재)
- 검색 API: 기업명·종목코드로 후보 조회
- 기업 기본정보 조회 API

## 1-2. DART 재무 데이터 연동

```text
corp_code → DART Open API → 정제 → SQLite(FinancialData)
```

- DART 재무제표·관련 공시 조회 서비스
- 응답 정제 후 `FinancialData` 저장 (`company_id`, `period`, metrics)
- Rate Limit 고려한 호출 최소화

## 1-3. 핵심 재무지표 계산 & 추세

PRD 주요 지표를 계산·제공한다.

- 매출, 영업이익, 순이익, 영업현금흐름, FCF
- ROE, ROIC, 영업이익률, 부채비율, 유동비율, 이자보상배율
- 매출·영업이익 성장률
- 최근 3~5년 추세 데이터 구성

## 1-4. 업종 특성 참고 데이터

- 업종 분류를 Company에 연결
- 업종별 지표 특성은 **정적 JSON**(예: `backend/data/industry_profiles.json`)으로 구축
- AI 프롬프트·분석 규칙에 “일반 기준 + 업종 특성 + 과거 추세” 반영
- MVP에서는 정교한 업종 Benchmark·실시간 API는 만들지 않음 (이후 교체 가능)

## 1-5. 종합 재무 분석 (rule / Groq)

```text
재무 데이터 + 업종 정보 + 과거 추세 → (rule | groq) → 구조화된 분석 결과
```

- AI: `ANALYSIS_PROVIDER=groq` + `GROQ_API_KEY` (실패 시 rule 폴백, 사용자에게 쿼터 문구 미노출)
- 로컬만: `ANALYSIS_PROVIDER=rule`
- Gemini/OpenAI 클라이언트 코드는 보존하나 기본 경로에서는 사용하지 않음
- 설정 상세: `docs/ANALYSIS_PROVIDER.md`

제공 항목:

- 기업 한줄 요약
- 재무 상태 요약
- 성장성 분석
- 주요 강점 / 위험요인
- 투자 체크포인트

원칙: 실제 수집 데이터에만 기반, 없는 수치·사실 생성 금지. 투자 권유 금지.

## 1-6. 기업 분석 Dashboard API

단일 진입 API(또는 소수 API 조합)로 Dashboard에 필요한 데이터를 반환.

```text
GET /companies/{company_id}/analysis  (예시)
→ 기본정보 + 재무지표 + 추세 + AI 분석
```

검색·(향후)추천 모두 이 API를 재사용한다.

## 1-7. 캐시·안정성

- 재무·분석 결과 캐시(메모리 또는 DB TTL)
- DART/Gemini(또는 캐시) 실패 시 캐시·명확한 에러/폴백 응답
- Retry / Rate Limit 기본 대응

---

# Phase 2. MVP 프론트엔드 (React)

목표: 기업 검색 후 **3분 이내**에 재무 상태·성장성을 이해할 수 있는 Dashboard.

## 2-1. 라우팅 & 기업 검색 UI

- React Router 설치·연결
  - `/` — 홈·검색
  - `/companies/:companyId` — 기업 분석 Dashboard
  - `/favorites` — 즐겨찾기(후속 Phase에서 사용, 라우트만 미리 둘 수 있음)
- 기업명 / 종목코드 검색 입력
- 검색 결과 목록 → `/companies/:companyId`로 이동

## 2-2. 기업 분석 Dashboard UI

한 화면에 표시:

```text
기업 기본정보
→ 주요 재무지표
→ 재무 추세 (3~5년, Recharts 간단 차트)
→ AI 재무 분석
→ 강점 / 위험요인 / 투자 체크포인트
```

- Recharts로 매출·영업이익 등 핵심 추세 라인/바 차트
- 로딩·에러·데이터 없음 상태 처리
- AI 해석과 원본 수치를 구분해서 표시
- 가능하면 데이터 기준일 표시

## 2-3. 홈·네비게이션 최소 정리

- 앱 이름(FinancePilot AI) 반영
- 검색 → Dashboard 동선만 MVP에 포함
- (추천·즐겨찾기는 Phase 4~5)

---

# Phase 3. MVP 검증·마무리

- 대표 종목으로 E2E 확인 (검색 → 지표 → AI 분석)
- API Key 미설정·외부 API 장애 시 안내 메시지 확인
- PRD 성공 기준 중 **분석 완료 시간 3분 이내**를 수동으로 점검
- `TASKS.md` MVP 항목 전부 체크 후 Phase 4로 진행

---

# Phase 4. MVP 이후 — 즐겨찾기

백엔드 → 프론트 순.

### 백엔드

- `Favorite` 모델: `user_id`, `company_id`, `created_at`
- 추가 / 제거 / 목록 API
- **`user_id`는 항상 `"local"` 고정**. 로그인·세션·JWT 등 인증은 구현하지 않음

### 프론트엔드

- Dashboard에서 즐겨찾기 추가·해제
- `/favorites` 목록 화면 → 기존 분석 Dashboard로 이동
- 알림 기능은 제외

---

# Phase 5. MVP 이후 — 추천 기업 (인기 테마)

백엔드 → 프론트 순.  
**별도 분석 로직을 만들지 않고**, 기존 `company_id` → 분석 API로 연결한다.

### 백엔드

- `Theme`, `ThemeStock`, (필요 시) `MarketData` 모델
- 인기 테마 산출 보조 데이터 연동 검토  
  - 네이버 데이터랩(검색 관심도)  
  - 시장 데이터(KRX 등 거래량·거래대금) — 도입 전 API 정책·승인 확인
- 규칙 기반 초기 추천 점수 (복잡한 AI 추천 모델 제외)
- 테마·추천 종목 조회 API

### 프론트엔드

- 홈에 “최근 인기 테마” / 테마별 추천 기업
- 종목 클릭 → 기존 기업 분석 Dashboard

---

# Phase 6. MVP 이후 — 최신 뉴스 분석

뉴스 API 공급자 선정 후에만 착수한다. MVP는 특정 뉴스 API에 의존하지 않는다.

### 백엔드

- 외부 뉴스 API 연동
- `News` 모델 저장 (제목, URL, 발행일, 요약, 감성 등)
- 중복 제거·정제
- OpenAI로 요약·긍정/중립/부정 분류
- 기업별 뉴스 조회 API

### 프론트엔드

- Dashboard에 최신 뉴스·요약·감성 섹션 추가

---

## 범위 밖 (이번 계획에서 구현하지 않음)

PRD §8 기준. 예:

- Quant Screener, 백테스트, 포트폴리오, 자동 매매
- 매수·매도 신호 / 투자 추천
- 모바일 앱, PDF 리포트, 메신저 알림
- 고도화된 실시간 주가·멀티 에이전트 리포트

---

## 권장 진행 방식

1. `docs/TASKS.md`에서 **미완료 MVP 항목 하나**만 선택해 구현한다.
2. 백엔드 API가 동작하는지 `/docs`(Swagger) 또는 curl로 확인한다.
3. 그다음 해당 API를 쓰는 프론트 UI를 붙인다.
4. 작업을 마치면 `TASKS.md` 체크박스를 업데이트한다.

실행 환경 참고:

- conda 환경: `finance`
- 백엔드: `cd backend` → `uvicorn main:app --reload`
- 프론트: `cd frontend` → `npm run dev`
