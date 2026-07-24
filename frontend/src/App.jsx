import { Link, NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { checkHealth } from './api'

export default function App() {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    checkHealth()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('fail'))
  }, [])

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand brand-ci" aria-label="FinancePilot AI 메인">
          <img
            src="/brand/financepilot-ci.png"
            alt="FinancePilot AI"
            className="brand-ci-img"
            width={36}
            height={36}
          />
          <span className="brand-ci-text">FinancePilot AI</span>
        </Link>
        <nav className="nav" aria-label="주요 메뉴">
          <NavLink to="/home">검색</NavLink>
          <NavLink to="/favorites">즐겨찾기</NavLink>
        </nav>
        <div className="conn" data-status={status}>
          {status === 'checking' && '연결 확인 중…'}
          {status === 'ok' && '서버 연결됨'}
          {status === 'fail' && '서버 연결 실패'}
        </div>
      </header>

      <main className="main">
        <Outlet />
      </main>

      <footer className="site-footer" aria-label="사이트 정보">
        <div className="site-footer-inner">
          <div className="site-footer-brand">
            <img
              src="/brand/financepilot-ci.png"
              alt=""
              className="site-footer-ci"
              width={40}
              height={40}
            />
            <div>
              <p className="site-footer-name">FinancePilot AI</p>
              <p className="site-footer-copy">
                Copyright 2026 FinancePilot AI Co., Ltd. All rights reserved.
              </p>
            </div>
          </div>

          <ul className="site-footer-links">
            <li>
              <span className="footer-link-dummy">개인정보처리방침</span>
            </li>
            <li>
              <span className="footer-link-dummy">신용정보활용체계</span>
            </li>
          </ul>

          <p className="site-footer-disclaimer">
            This website provides dummy legal notices for UI demonstration only.
            No interactive features are available.
          </p>
        </div>
      </footer>
    </div>
  )
}
