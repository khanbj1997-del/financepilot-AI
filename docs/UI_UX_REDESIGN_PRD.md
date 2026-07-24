# FinancePilot AI — UI/UX Redesign PRD

## 1. 프로젝트 개요

**FinancePilot AI**는 특정 기업을 검색하면 해당 기업의 재무제표와 재무 데이터를 기반으로 주요 재무지표를 보여주고, AI가 재무 상태를 분석하여 핵심 Insight를 제공하는 금융 분석 서비스다.

현재 핵심 기능은 이미 Frontend와 Backend에 구현되어 있다.

이번 프로젝트의 목적은 **기존 기능을 변경하거나 새로운 기능을 추가하는 것이 아니라, 현재 구현된 Frontend의 UI/UX와 시각적 완성도를 개선하는 것**이다.

핵심 사용자 흐름은 다음과 같다.

```text
기업 검색
→ 기업 Dashboard
→ AI Insight 확인
→ 주요 재무지표 확인
→ 재무 차트 확인
→ AI 재무 분석 확인
→ 즐겨찾기
```

---

## 2. 프로젝트 목표

FinancePilot AI를 다음과 같은 인상을 주는 서비스로 리디자인한다.

* 전문적인 금융 분석 서비스
* 현대적인 AI SaaS
* 신뢰감 있는 데이터 서비스
* 깔끔하고 직관적인 Dashboard
* 복잡한 재무 데이터를 쉽게 이해할 수 있는 UI

사용자가 페이지를 처음 방문했을 때 **"기업을 검색하고, AI가 분석한 핵심 내용을 쉽게 확인하는 서비스"**라는 것을 즉시 이해할 수 있어야 한다.

---

## 3. 가장 중요한 원칙

### 기존 기능은 절대 변경하지 않는다.

이번 작업은 **Frontend UI/UX Redesign**에만 집중한다.

반드시 유지해야 한다.

* 기존 Backend
* 기존 API
* 기존 API 호출 로직
* 기존 데이터 구조
* 기존 재무 계산 로직
* 기존 AI 분석 로직
* 기존 검색 기능
* 기존 Dashboard 기능
* 기존 차트
* 기존 Insight
* 기존 즐겨찾기
* 기존 Routing

다음 작업은 하지 않는다.

* Backend 수정
* API 변경 또는 추가
* 새로운 기능 개발
* 새로운 외부 API 연동
* Mock 데이터 추가
* AI 분석 로직 변경
* 재무 계산 로직 변경
* 기존 기능 삭제

**기존 데이터와 기능을 그대로 사용하고, 화면에 표현되는 방식만 개선한다.**

---

## 4. Design Direction

FinancePilot AI의 디자인은 다음 두 가지를 결합한다.

```text
Modern AI SaaS
+
Financial Intelligence
```

### 핵심 키워드

* Professional
* Clean
* Modern
* Premium
* Data-driven
* Trustworthy

전통적인 증권사 HTS처럼 복잡한 UI는 지양한다.

또한 과도한 Gradient, Glassmorphism, Neon, 애니메이션 등 장식적인 요소도 지양한다.

**깔끔한 금융 Dashboard + 현대적인 AI 서비스**의 느낌을 목표로 한다.

---

## 5. Global UI Design

전체 페이지에 일관된 디자인 시스템을 적용한다.

### Color

* Deep Navy / Dark Blue: 브랜드 및 주요 CTA
* Soft Gray / Off White: 페이지 배경
* White: Card 및 콘텐츠 영역
* Dark Charcoal: 주요 텍스트
* Muted Gray: 보조 텍스트
* Green: 긍정적 변화
* Red: 부정적 변화
* Amber: 주의 및 위험

색상은 장식보다 정보 전달을 위해 사용한다.

### Typography

명확한 정보 계층을 만든다.

```text
Page Title
→ Section Title
→ Card Title
→ Body
→ Caption
```

재무지표의 핵심 숫자는 충분히 크게 표시하여 빠르게 인식할 수 있도록 한다.

### Layout

* 충분한 여백
* 일관된 Spacing
* 통일된 Card
* 절제된 Border와 Shadow
* 명확한 정보 계층

을 적용한다.

---

## 6. Home UI/UX

Home은 사용자가 서비스를 이해하고 기업 검색을 시작하는 화면이다.

가장 중요한 CTA는 **기업 검색**이다.

권장 구조:

```text
FinancePilot AI
기업의 재무를 AI로 쉽게 이해하세요.

복잡한 재무 데이터를 분석하고
핵심 Insight를 한눈에 확인하세요.

[ 기업명 또는 종목코드 검색 ]
```

기존 검색 기능은 그대로 유지하면서 Search Input의 디자인과 사용성을 개선한다.

기존에 존재하는 최근 검색, 즐겨찾기, 인기 테마 등의 UI가 있다면 기능은 유지하고 디자인만 개선한다.

---

## 7. Company Dashboard UI/UX

Dashboard는 서비스의 핵심 화면이다.

정보의 시각적 우선순위를 다음과 같이 구성한다.

```text
Company Header
↓
AI Key Insight
↓
Key Financial Metrics
↓
Financial Trends / Charts
↓
AI Financial Analysis
↓
Strengths / Risks
```

### Company Header

* 기업명
* 종목코드
* 업종
* 기존 기업 정보
* 즐겨찾기 버튼

을 명확하게 표현한다.

### AI Insight

사용자가 가장 먼저 핵심 내용을 이해할 수 있도록 Dashboard에서 눈에 잘 띄는 영역으로 디자인한다.

### Financial Metrics

기존 재무지표 데이터를 Card 형태로 보기 쉽게 표현한다.

```text
지표명
핵심 수치
변화율
기간 또는 설명
```

### Financial Charts

기존 차트와 데이터를 유지한다.

차트의 제목, 단위, 기간, Legend 등을 명확하게 표현하여 사용자가 재무 추세를 쉽게 이해하도록 한다.

### AI Analysis

기존 AI 분석 결과를 긴 텍스트 덩어리처럼 보이지 않도록 적절한 Section과 Card로 시각적으로 구조화한다.

### Strengths / Risks

기존 분석 결과의 강점과 위험요인을 명확하게 구분하여 핵심 내용을 빠르게 파악할 수 있도록 한다.

---

## 8. Favorites UI

기존 즐겨찾기 기능을 유지한다.

기업 목록을 Card 또는 List 형태로 보기 쉽게 리디자인한다.

다음 UI 상태를 명확하게 표현한다.

* Favorite
* Hover
* Active
* Empty State

즐겨찾기 기업을 클릭하면 기존 Dashboard로 이동하는 기능은 그대로 유지한다.

---

## 9. UX Polish

기존 기능을 유지하면서 다음 UI 상태를 개선한다.

* Loading State
* Skeleton UI
* Error State
* Empty State
* Hover State
* Focus State
* Button State
* Favorite Interaction

애니메이션은 최소화하고 금융 분석 서비스에 적합한 절제된 Micro Interaction만 사용한다.

---

## 10. Responsive Design

Desktop을 우선으로 디자인한다.

단, 기존 UI가 Tablet과 Mobile에서도 자연스럽게 보이도록 기본적인 Responsive Design을 적용한다.

특히 다음 요소가 작은 화면에서도 깨지지 않도록 한다.

* Header
* Search
* Metric Cards
* Charts
* AI Analysis
* Favorites

---

## 11. Final Goal

최종 결과물은 다음과 같은 사용자 경험을 제공해야 한다.

> **"FinancePilot AI는 복잡한 기업 재무 데이터를 AI가 분석하고, 중요한 내용을 누구나 쉽게 이해할 수 있도록 정리해주는 전문적인 금융 AI 서비스다."**

이번 프로젝트의 성공 기준은 **새로운 기능을 많이 추가하는 것이 아니라, 현재 구현된 기능을 훨씬 더 아름답고 전문적이며 사용하기 편하게 만드는 것**이다.

**기존 기능과 데이터는 그대로 유지하고, Frontend의 디자인과 사용자 경험만 개선한다.**
