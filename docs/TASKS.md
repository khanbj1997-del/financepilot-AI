# FinancePilot AI 작업 목록

`docs/DEVELOPMENT_PLAN.md`와 `docs/PRD.md`를 기준으로 한다.  
한 항목 = 한 번에 처리할 하나의 작업 단위.  
완료하면 `[ ]` → `[x]`로 바꾼다.

> **UI/UX Redesign**은 별도 문서로 관리한다.  
> - PRD: `docs/UI_UX_REDESIGN_PRD.md`  
> - 작업 목록: `docs/UI_UX_TASKS.md`

프로젝트 생성·conda·scaffold는 완료된 것으로 보고 **포함하지 않는다**.

---

# A. MVP 작업

## A0. 공통 기반

- [x] `backend/.env` 파일 생성 (`DART_API_KEY`, `OPENAI_API_KEY` 키 기입용)
- [x] `.env.example`에 동일 키 항목 문서화
- [x] 백엔드에 `.env` 로드 설정 (`python-dotenv`)
- [x] 백엔드 모듈 폴더 구조 정리 (`models` / `schemas` / `services` / `routers` 등)
- [x] 프론트 `api.js`를 백엔드 전용 API 클라이언트로 확장할 준비 (base URL 등)
- [x] React Router 설치 및 초기 라우트 골격 (`/`, `/companies/:companyId`, `/favorites`)

---

## A1. Company Master & 기업 검색 (백엔드)

- [x] `Company` SQLModel 정의 (`company_id`, `company_name`, `stock_code`, `corp_code`, `industry`)
- [x] DART corp_code 매핑 데이터 수집·로드 방식 구현 (기동 시 또는 DB 적재)
- [x] Company Master를 SQLite에 저장·조회하는 서비스 작성
- [x] 기업명 검색 API 구현
- [x] 종목코드 검색 API 구현
- [x] 기업 기본정보 조회 API 구현 (`company_id` 기준)
- [x] 검색 중복 제거 (종목코드 corp 오탐 수정, 동일 기업명·구 corp `modify_date` 기준 정리)

---

## A2. DART 재무 데이터 연동 (백엔드)

- [x] DART Open API 클라이언트 작성 (키·공통 요청 처리)
- [x] 재무제표 조회 연동
- [x] DART 응답을 내부 스키마로 정제하는 로직 작성
- [x] `FinancialData` 모델 정의 및 SQLite 저장
- [x] `company_id` 기준 재무 데이터 조회 API 구현
- [x] DART Rate Limit·실패에 대한 기본 에러 처리

---

## A3. 재무지표 계산 & 추세 (백엔드)

- [x] 핵심 지표 계산: 매출, 영업이익, 순이익
- [x] 핵심 지표 계산: 영업현금흐름, FCF
- [x] 핵심 지표 계산: ROE, ROIC, 영업이익률
- [x] 핵심 지표 계산: 부채비율, 유동비율, 이자보상배율
- [x] 매출·영업이익 성장률 계산
- [x] 최근 3~5년 추세 데이터 구성 API/응답 필드 추가

---

## A4. 업종 특성 참고 데이터 (백엔드)

- [x] Company에 업종(`industry`) 연결·조회 확인
- [x] 업종별 지표 특성 **정적 JSON** 초안 구축 (예: `backend/data/industry_profiles.json`)
- [x] 분석 시 정적 JSON을 불러오는 서비스 작성
- [x] AI 프롬프트(또는 분석 규칙)에 “일반 기준 + 업종 + 추세” 반영 포인트 정의
- [x] DART corpCode 미분류 덮어쓰기 수정 + company.json 업종코드 매핑 + 미분류 시 Groq 추정·캐시

---

## A5. 종합 재무 분석 (백엔드)

- [x] OpenAI API 클라이언트 작성 (키는 `.env`만 사용, 코드 유지·기본 미사용)
- [x] Gemini API Provider 추가 (코드 유지·기본 미사용)
- [x] Groq API Provider 추가 (`GROQ_API_KEY`, 실패 시 rule 폴백) — 권장 AI
- [x] 분석 입력 페이로드 구성 (재무 + 업종 + 추세)
- [x] 구조화 출력 스키마 정의 (종합 판단, 재무건전성, 수익성, 성장성, 이익의 질, 강점, 위험, 투자 질문, 확인 데이터)
- [x] AI가 없는 수치를 만들지 않도록 프롬프트·검증 규칙 적용
- [x] 기업 종합 분석 API 구현
- [x] 분석 결과 캐시(동일 기업·동일 기준 데이터 재요청 시) 기본 적용
- [x] Provider 설정 문서 (`docs/ANALYSIS_PROVIDER.md`)
- [x] 분석 결과 구조를 투자 의사결정용 9섹션으로 개편 (관계·추세·상반지표·확인포인트)
- [x] 전년 동기(동일 분기/반기/연간) 성장률 계산·프롬프트 반영 + 한국어 전용 출력 규칙
- [x] 지표 간 관계 분석·종합판단 중복 제거·유동비율 극단값 균형 해석·투자질문 품질 개선 (schema v5)
- [x] 결론 우선 종합판단·업종 맥락 구체화·한자 검증 강화·외부검색 슬롯(미연동) (schema v6)
- [x] 금액·비율 표시 포맷 통일 (조/억/만 + %, schema v7)

---

## A6. 기업 분석 Dashboard API 통합 (백엔드)

- [x] Dashboard용 통합 응답 스키마 정의 (기본정보 + 지표 + 추세 + AI 분석)
- [x] `company_id` 기준 통합 분석 API 구현
- [x] 검색으로 얻은 `company_id`만으로 통합 API가 동작하는지 확인
- [x] 외부 API 장애 시 캐시/부분 데이터·에러 메시지 정책 정리

---

## A7. 기업 검색 UI (프론트엔드)

- [x] 앱 타이틀·홈을 FinancePilot AI 기준으로 정리
- [x] 기업명/종목코드 검색 입력 UI 구현
- [x] 검색 API 연동 및 결과 목록 표시
- [x] 결과 선택 시 `/companies/:companyId`로 이동
- [x] 검색 로딩·결과 없음·API 실패 상태 UI

---

## A8. 기업 분석 Dashboard UI (프론트엔드)

- [x] 기업 기본정보 섹션
- [x] 주요 재무지표 섹션
- [x] 최근 3~5년 재무 추세 섹션 (숫자 + **Recharts** 간단 차트)
- [x] AI 종합 분석 섹션 (종합 판단·재무건전성·수익성·성장성·이익의 질·강점·위험·투자 질문·확인 데이터)
- [x] 주요 강점 / 위험요인 / 투자 질문·확인 데이터 섹션
- [x] AI 해석과 원본 수치·데이터 기준일 구분 표시
- [x] Dashboard 로딩·에러·데이터 없음 상태 UI
- [x] 통합 분석 API 연동으로 화면 E2E 연결
- [x] 연결/개별 재무제표 배지 표시
- [x] 연간·분기 추세 탭 분리
- [x] 영업손실 계정 파싱 및 fs_div 일관성 (예: 리튬포어스)

---

## A9. MVP 검증

- [x] 대표 종목 1~2개로 검색 → Dashboard → AI 분석 전체 흐름 확인
- [x] API Key 미설정 시 안내가 뜨는지 확인
- [x] DART/OpenAI 실패 시 사용자 메시지가 적절한지 확인
- [x] “3분 이내 핵심 파악” 목표를 수동으로 점검

### A9 검증 결과 (2026-07-24)

| 항목 | 결과 |
|------|------|
| health | PASS |
| 삼성전자 검색 → Dashboard(지표·분석) | PASS (`source=rule`, partial=false) |
| SK하이닉스 종목코드 검색 → Dashboard | PASS |
| 없는 기업 404 | PASS |
| rule 안내는 `notices`, 실패는 `warnings` | PASS |
| Dashboard API 응답 시간 | ~0.02s (3분 목표 충족) |
| OpenAI | MVP는 `ANALYSIS_PROVIDER=rule` (크레딧 미사용, 의도된 동작) |

프론트 E2E: `npm run dev` → 검색 → Dashboard 화면에서 동일 흐름 수동 확인 가능.

---

# B. MVP 이후 작업

> A9까지 완료한 뒤에만 진행한다.

## B1. 즐겨찾기 (백엔드)

- [x] `Favorite` 모델 정의 (`user_id`, `company_id`, `created_at`)
- [x] `user_id = "local"` 고정 (로그인·인증 없음, 단일 사용자)
- [x] 즐겨찾기 추가 API
- [x] 즐겨찾기 제거 API
- [x] 즐겨찾기 목록 조회 API (`user_id=local` 기준)

---

## B2. 즐겨찾기 (프론트엔드)

- [x] Dashboard에서 즐겨찾기 추가/해제 UI
- [x] `/favorites` 즐겨찾기 목록 화면
- [x] 목록에서 `/companies/:companyId` 분석 Dashboard로 이동
- [x] 즐겨찾기 API 연동 및 실패 상태 처리

---

## B3. 추천 기업 — 데이터·백엔드

- [x] `Theme`, `ThemeStock` 모델 정의
- [x] (필요 시) `MarketData` 모델 정의
- [x] 네이버 데이터랩 등 검색 관심도 데이터 연동 가능 여부 확인 후 연동 — 확인: API HUB 이관·키 검증 전 → **미연동**, 시드+규칙 폴백
- [x] 시장 데이터(KRX 등) API 정책·승인·호출 제한 확인 후 연동 — 확인: 키+API별 승인 필요·일 1만회 → **미연동**, `MarketData`만 예약
- [x] 규칙 기반 인기 테마·추천 종목 산출 로직 구현 (`themes_seed` + Company.industry)
- [x] 테마 목록 / 테마별 추천 기업 API 구현 (`GET /themes`, `GET /themes/{id}/stocks`)
- [x] 추천 종목 클릭 시 기존 `company_id` 분석 API로 연결됨을 확인

---

## B4. 추천 기업 — 프론트엔드

- [x] 홈에 최근 인기 테마 섹션 UI
- [x] 테마별 추천 기업 목록 UI
- [x] 추천 기업 선택 → 기존 분석 Dashboard 이동
- [x] 추천 API 연동 및 로딩·빈 목록·실패 상태 UI

---

## B5. 최신 뉴스 분석 — 준비·백엔드

> **보류:** 뉴스 API 접근 불가. 가능해지면 재개.

- [ ] 외부 뉴스 API 후보 조사 (한국 기업 뉴스, 비용, 저장·재사용 조건)
- [ ] 뉴스 API 선정 및 `.env` 키 항목 추가
- [ ] `News` 모델 정의
- [ ] 기업별 뉴스 수집 서비스 구현
- [ ] 뉴스 정제·중복 제거
- [ ] OpenAI 뉴스 요약·감성(긍정/중립/부정) 분석
- [ ] 기업별 뉴스 조회 API 구현

---

## B6. 최신 뉴스 분석 — 프론트엔드

> B5 미완료로 **자리만 확보**. API 연동·실제 뉴스 UI는 B5 이후.

- [x] Dashboard에 최신 뉴스 섹션 추가 (준비중 플레이스홀더)
- [x] 뉴스 요약·감성·원문 링크 표시 — 추후 연동 예정 안내로 대체
- [x] 뉴스 API 연동 및 로딩·빈 목록·실패 상태 UI — 준비중 문구로 대체

---

# C. 범위 밖 (체크하지 않음 · 구현하지 않음)

- Quant Screener / 백테스트 / 포트폴리오 / 자동 매매
- 매수·매도 신호 및 투자 추천
- 모바일 앱 / PDF 리포트 / 메신저 알림
- 고도화 실시간 주가·멀티 에이전트 리포트
- 로그인·회원·인증 시스템 (즐겨찾기는 `user_id="local"` 고정만 사용)
- 알림(실적·뉴스 모멘텀 등) — 즐겨찾기 확장 후보이나 초기 범위 제외

---

# D. 배포 전 체크리스트 (개발 완료 후 진행)

> MVP 로컬 개발이 끝난 뒤, 배포 직전에 다시 확인한다.

- [x] `.env`에서 `ANALYSIS_PROVIDER=groq` 전환
- [x] 유효한 `GROQ_API_KEY` 확인 후 `source=groq` 실사용 확인
- [x] `/companies/{id}/analysis?refresh=true` 호출 시 `source=groq` 확인
- [ ] DART Rate Limit·캐시 TTL 운영 값 점검
