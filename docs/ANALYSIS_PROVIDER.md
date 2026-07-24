# 분석 Provider 설정 (rule / groq)

FinancePilot AI의 종합 재무 분석은 `ANALYSIS_PROVIDER`로 엔진을 고른다.

## 옵션

| 값 | 동작 |
|----|------|
| `groq` (권장 AI) | Groq API로 구조화 JSON 분석. 실패·키 없음 → **rule 폴백** (상세 오류는 서버 로그만). |
| `rule` | 로컬 규칙 엔진. 외부 LLM 호출 없음. |
| `gemini` | Google Gemini 경로 코드 유지. 기본 미사용. |
| `openai` | OpenAI 경로 코드 유지. 기본 미사용. |

분석 결과 스키마(종합 판단·재무 건전성·수익성·성장성·이익의 질·강점·위험·투자 질문·확인 데이터)와 Dashboard UI는 Provider와 무관하게 동일하다. 화면에는 **분석: AI** / **분석: 규칙 기반**만 표시한다.

## 환경변수 (`backend/.env`)

```env
GROQ_API_KEY=발급받은_키
GROQ_MODEL=llama-3.3-70b-versatile
ANALYSIS_PROVIDER=groq
```

- 키는 코드에 넣지 말고 `.env`에만 둔다.
- `backend/.env.example`을 복사해 시작하면 된다.

## 패키지

Groq 호출은 기존 `requests`만 사용한다 (OpenAI 호환 Chat Completions). **추가 pip 패키지 불필요.**

```bash
cd backend
pip install -r requirements.txt
```

## 전환·확인

1. `.env`에 `GROQ_API_KEY` 설정
2. `ANALYSIS_PROVIDER=groq`
3. 확인 예:

```http
GET /companies/{company_id}/analysis?refresh=true
```

응답 `source`가 `groq`이면 성공. 실패 시 `source=rule`로 폴백하며 서버는 중단되지 않는다. 사용자에게는 쿼터/HTTP 상세를 보여주지 않는다.

## rule로 되돌리기

```env
ANALYSIS_PROVIDER=rule
```
