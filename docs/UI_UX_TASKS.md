# FinancePilot AI — UI/UX Redesign 작업 목록

`docs/UI_UX_REDESIGN_PRD.md`를 기준으로 한다.  
한 항목 = 한 번에 처리할 하나의 작업 단위.  
완료하면 `[ ]` → `[x]`로 바꾼다.

## 작업 원칙 (매 작업 전 확인)

- Frontend UI/UX만 변경한다.
- Backend / API / 데이터 / 계산 / AI 로직 / Routing / 기능 추가·삭제는 하지 않는다.
- 기존 API 응답을 그대로 화면에 표현하는 방식만 개선한다.

---

# U0. 디자인 시스템 기반

- [x] 전역 CSS 변수 정의 (Navy, Soft Gray, White, Charcoal, Muted, Green, Red, Amber)
- [x] Typography 스케일 정리 (Page / Section / Card / Body / Caption)
- [x] Spacing·Card·Border·Shadow 토큰을 공통 클래스로 정리
- [x] 앱 공통 Header(브랜드·네비) 시각 계층만 리디자인 (기능·라우트 유지)

---

# U1. Home UI/UX

- [x] Home 히어로 카피·구조 정리 (브랜드 → 가치 제안 → 검색 CTA)
- [x] Search Input 디자인·포커스·사용성 개선 (검색 API·로직 유지)
- [x] 검색 결과 목록 UI 리디자인 (로딩·빈 결과·에러 상태 포함)
- [x] 인기 테마·추천 기업 영역이 있다면 **디자인만** 개선 (기능·API 유지)
- [x] Home이 “검색 → AI 분석” 서비스임을 첫 화면에서 이해되게 점검

---

# U1b. Trust Landing (메인 인트로)

- [x] `/` 신뢰 메인 랜딩 (풀블리드 이미지 + 브랜드 + 신뢰 문구 + CTA)
- [x] CTA「서비스 시작하기」→ `/home` (기존 검색 홈)
- [x] CI/네비: 브랜드 → `/`, 검색 → `/home`
- [x] 교육용 랜딩 배경 이미지·CREDITS 표기

---

# U2. Company Dashboard — 레이아웃·헤더

- [x] Dashboard 시각 우선순위 재배치 (Header → Insight → Metrics → Charts → Analysis → Strengths/Risks)
- [x] Company Header 리디자인 (기업명·종목코드·업종·기존정보·즐겨찾기)
- [x] Dashboard 섹션 여백·카드·정보 계층 통일

---

# U3. Company Dashboard — Insight·지표·차트

- [x] AI Key Insight를 Dashboard 상단 강조 영역으로 디자인
- [x] Key Financial Metrics를 Card 형태(지표명·수치·변화율·기간)로 표현
- [x] 재무 차트 제목·단위·기간·Legend 가독성 개선 (차트 라이브러리·데이터 유지)

---

# U4. Company Dashboard — AI 분석·강점/위험

- [x] AI 분석 본문을 Section/Card로 구조화 (긴 텍스트 덩어리 해소)
- [x] Strengths / Risks를 시각적으로 명확히 구분
- [x] 뉴스 등 “준비중” 플레이스홀더가 있다면 톤만 디자인 시스템에 맞춤

---

# U5. Favorites UI

- [x] 즐겨찾기 목록을 Card 또는 List로 리디자인
- [x] Favorite / Hover / Active / Empty State 명확화
- [x] 목록 → Dashboard 이동 동작 유지 확인

---

# U6. UX Polish

- [x] Loading / Skeleton UI 개선
- [x] Error / Empty State 개선
- [x] Button / Focus / Hover / Favorite Interaction 절제된 polish
- [x] 과도한 애니메이션 없이 Micro Interaction만 적용

---

# U7. Responsive

- [x] Desktop 기준 레이아웃 최종 정리
- [x] Tablet·Mobile에서 Header / Search / Metric Cards / Charts / Analysis / Favorites 깨짐 점검·수정

---

# U8. 최종 검증

- [x] 검색 → Dashboard → Insight → 지표 → 차트 → AI 분석 → 즐겨찾기 흐름 수동 확인 (코드·라우트·API 호출 경로 점검)
- [x] Backend/API 호출·응답이 redesign 전과 동일한지 확인 (`api.js` 엔드포인트 유지)
- [x] PRD Final Goal 인상(전문적·쉬운 이해)을 Home·Dashboard에서 점검

---

# 범위 밖 (이 문서에서 구현하지 않음)

- Backend / API 변경·추가
- 신규 기능·외부 API·Mock 데이터
- AI·재무 계산 로직 변경
- 기존 기능 삭제
