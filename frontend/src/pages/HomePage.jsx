import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getThemeStocks, listThemes, searchCompanies } from '../api'
import { HOME_NOTICES, NOTICE_DISPLAY_LIMIT } from '../data/notices'

const THEME_STOCK_LIMIT = 5

const HERO_IMAGES = [
  '/media/hero-city.jpg',
  '/media/hero-office.jpg',
  '/media/hero-finance.jpg',
  '/media/hero-business.jpg',
]

export default function HomePage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [items, setItems] = useState([])
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [heroIndex, setHeroIndex] = useState(0)
  const [videoReady, setVideoReady] = useState(false)

  const [themeStatus, setThemeStatus] = useState('loading')
  const [themeError, setThemeError] = useState('')
  const [themeMessage, setThemeMessage] = useState('')
  const [themes, setThemes] = useState([])
  const [activeThemeId, setActiveThemeId] = useState(null)
  const [stockStatus, setStockStatus] = useState('idle')
  const [stockError, setStockError] = useState('')
  const [stocks, setStocks] = useState([])

  useEffect(() => {
    // Optional local video (if user places hero-city.mp4/webm)
    let cancelled = false
    Promise.any([
      fetch('/media/hero-city.mp4', { method: 'HEAD' }).then((r) => {
        if (!r.ok) throw new Error('no mp4')
        return 'mp4'
      }),
      fetch('/media/hero-city.webm', { method: 'HEAD' }).then((r) => {
        if (!r.ok) throw new Error('no webm')
        return 'webm'
      }),
    ])
      .then(() => {
        if (!cancelled) setVideoReady(true)
      })
      .catch(() => {
        if (!cancelled) setVideoReady(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (videoReady) return undefined
    const timer = setInterval(() => {
      setHeroIndex((i) => (i + 1) % HERO_IMAGES.length)
    }, 6500)
    return () => clearInterval(timer)
  }, [videoReady])

  useEffect(() => {
    let cancelled = false
    setThemeStatus('loading')
    setThemeError('')
    listThemes()
      .then((res) => {
        if (cancelled) return
        const list = res.items || []
        setThemes(list)
        setThemeMessage(res.message || '')
        if (!list.length) {
          setThemeStatus('empty')
          return
        }
        setThemeStatus('ok')
        setActiveThemeId(list[0].theme_id)
      })
      .catch((err) => {
        if (cancelled) return
        setThemes([])
        setThemeStatus('error')
        setThemeError(err.message || '인기 테마를 불러오지 못했습니다.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!activeThemeId) {
      setStocks([])
      setStockStatus('idle')
      return undefined
    }
    let cancelled = false
    setStockStatus('loading')
    setStockError('')
    getThemeStocks(activeThemeId, THEME_STOCK_LIMIT)
      .then((res) => {
        if (cancelled) return
        const list = (res.items || []).slice(0, THEME_STOCK_LIMIT)
        setStocks(list)
        setStockStatus(list.length ? 'ok' : 'empty')
      })
      .catch((err) => {
        if (cancelled) return
        setStocks([])
        setStockStatus('error')
        setStockError(err.message || '추천 기업을 불러오지 못했습니다.')
      })
    return () => {
      cancelled = true
    }
  }, [activeThemeId])

  useEffect(() => {
    const q = query.trim()
    if (q.length < 1) {
      setItems([])
      setStatus('idle')
      setError('')
      return undefined
    }

    const timer = setTimeout(async () => {
      setStatus('loading')
      setError('')
      try {
        const data = await searchCompanies(q)
        const list = data.items || []
        setItems(list)
        setStatus(list.length ? 'ok' : 'empty')
      } catch (err) {
        setItems([])
        setStatus('error')
        setError(err.message || '검색에 실패했습니다.')
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [query])

  function onSubmit(e) {
    e.preventDefault()
    if (items.length === 1) {
      navigate(`/companies/${items[0].company_id}`)
    }
  }

  const activeTheme = themes.find((t) => t.theme_id === activeThemeId)

  return (
    <section className="page page-home">
      <div className="home-hero home-hero-media">
        <div className="home-hero-media-layer" aria-hidden="true">
          {videoReady ? (
            <video
              className="home-hero-video"
              autoPlay
              muted
              loop
              playsInline
              poster="/media/hero-city.jpg"
            >
              <source src="/media/hero-city.webm" type="video/webm" />
              <source src="/media/hero-city.mp4" type="video/mp4" />
            </video>
          ) : (
            HERO_IMAGES.map((src, i) => (
              <div
                key={src}
                className={`home-hero-slide ${i === heroIndex ? 'is-active' : ''}`}
                style={{ backgroundImage: `url(${src})` }}
              />
            ))
          )}
          <div className="home-hero-overlay" />
        </div>

        <div className="home-hero-content">
          <p className="home-brand">FinancePilot AI</p>
          <h1 className="page-title">기업의 재무를 AI로 쉽게 이해하세요</h1>
          <p className="home-value">
            복잡한 재무 데이터를 분석하고 핵심 Insight를 한눈에 확인하세요.
          </p>
          <p className="home-sub">
            기업명 또는 종목코드로 검색하면 재무지표, 추세 차트, AI 재무 분석을 바로
            확인할 수 있습니다.
          </p>

          <form className="home-search" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="company-search">
              기업명 또는 종목코드
            </label>
            <input
              id="company-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="기업명 또는 종목코드 검색"
              autoComplete="off"
              autoFocus
            />
            <button type="submit" disabled={status === 'loading'}>
              {status === 'loading' ? '검색 중…' : '검색'}
            </button>
          </form>
        </div>
      </div>

      {status === 'loading' && (
        <div className="skeleton-stack" aria-live="polite" aria-busy="true">
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-card" />
        </div>
      )}
      {status === 'empty' && (
        <div className="empty-panel">
          <p>검색 결과가 없습니다.</p>
          <p className="muted">기업명 또는 6자리 종목코드를 확인해 주세요.</p>
        </div>
      )}
      {status === 'error' && (
        <div className="banner warn">
          <p>{error}</p>
        </div>
      )}

      {status === 'ok' && (
        <ul className="result-list">
          {items.map((item) => (
            <li key={item.company_id}>
              <Link to={`/companies/${item.company_id}`} className="result-item">
                <span className="result-name">{item.company_name}</span>
                <span className="result-meta">
                  {item.stock_code || '-'} · {item.industry || '업종 미분류'}
                  {item.industry && item.industry_source === 'groq' ? ' (AI 추정)' : ''}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {status === 'idle' && (
        <p className="hint-text">예: 삼성전자, 005930</p>
      )}

      <section className="notice-section" aria-labelledby="notice-heading">
        <div className="notice-section-head">
          <h2 id="notice-heading" className="section-title">
            공지사항
          </h2>
          <span className="theme-count-hint">최대 {NOTICE_DISPLAY_LIMIT}건</span>
        </div>
        <ul className="notice-list">
          {HOME_NOTICES.slice(0, NOTICE_DISPLAY_LIMIT).map((item) => (
            <li key={item.id} className="notice-item">
              <span className="notice-date">{item.date}</span>
              <span className="notice-title">{item.title}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="theme-section" aria-labelledby="theme-heading">
        <div className="theme-section-head">
          <h2 id="theme-heading" className="section-title">
            최근 인기 테마
          </h2>
          <span className="theme-count-hint">테마별 추천 기업</span>
        </div>
        {themeMessage && themeStatus === 'ok' && (
          <p className="theme-note">{themeMessage}</p>
        )}

        {themeStatus === 'loading' && (
          <div className="skeleton-stack">
            <div className="skeleton skeleton-line" />
            <div className="skeleton skeleton-card" />
          </div>
        )}
        {themeStatus === 'empty' && (
          <div className="empty-panel">
            <p>표시할 인기 테마가 없습니다.</p>
          </div>
        )}
        {themeStatus === 'error' && (
          <div className="banner warn">
            <p>{themeError}</p>
          </div>
        )}

        {themeStatus === 'ok' && (
          <>
            <div className="theme-chips" role="tablist" aria-label="인기 테마">
              {themes.map((theme) => (
                <button
                  key={theme.theme_id}
                  type="button"
                  role="tab"
                  aria-selected={theme.theme_id === activeThemeId}
                  className={`theme-chip ${
                    theme.theme_id === activeThemeId ? 'is-active' : ''
                  }`}
                  onClick={() => setActiveThemeId(theme.theme_id)}
                >
                  {theme.theme_name}
                </button>
              ))}
            </div>

            {activeTheme?.description && (
              <p className="theme-desc">{activeTheme.description}</p>
            )}

            {stockStatus === 'loading' && (
              <div className="skeleton-stack">
                <div className="skeleton skeleton-line" />
                <div className="skeleton skeleton-line" />
              </div>
            )}
            {stockStatus === 'empty' && (
              <p className="state">이 테마에 추천 기업이 없습니다.</p>
            )}
            {stockStatus === 'error' && (
              <div className="banner warn">
                <p>{stockError}</p>
              </div>
            )}
            {stockStatus === 'ok' && (
              <ul className="result-list theme-stock-list">
                {stocks.map((item, idx) => {
                  const company = item.company
                  const name = company?.company_name || item.company_id
                  const meta = [
                    company?.stock_code || '-',
                    company?.industry || '업종 미분류',
                  ].join(' · ')
                  return (
                    <li key={item.company_id}>
                      <Link
                        to={`/companies/${item.company_id}`}
                        className="result-item theme-stock-item"
                      >
                        <span className="theme-rank" aria-hidden="true">
                          {idx + 1}
                        </span>
                        <span className="theme-stock-body">
                          <span className="result-name">{name}</span>
                          <span className="result-meta">{meta}</span>
                        </span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </>
        )}
      </section>
    </section>
  )
}
