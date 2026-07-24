import { Link } from 'react-router-dom'

export default function LandingPage() {
  return (
    <section className="landing" aria-label="FinancePilot AI 메인">
      <div
        className="landing-media"
        style={{ backgroundImage: 'url(/media/landing-trust.jpg)' }}
        aria-hidden="true"
      />
      <div className="landing-scrim" aria-hidden="true" />

      <div className="landing-content">
        <p className="landing-brand">FinancePilot AI</p>
        <h1 className="landing-headline">든든한 AI 분석 파트너</h1>
        <p className="landing-support">
          FinancePilot AI가 고객님의 투자 판단과 함께 걸어갑니다.
        </p>
        <div className="landing-cta">
          <Link to="/home" className="landing-cta-btn">
            서비스 시작하기
          </Link>
        </div>
      </div>
    </section>
  )
}
