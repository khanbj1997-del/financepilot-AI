import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  addFavorite,
  getCompanyDashboard,
  getFavoriteStatus,
  removeFavorite,
} from '../api'
import TrendChart from '../components/TrendChart'
import { formatAmount, formatPercent, formatRatio, formatPeriod } from '../utils/format'

function statementLabel(fsDiv, metaType) {
  if (metaType === '연결' || metaType === '개별') return metaType
  if (fsDiv === 'CFS') return '연결'
  if (fsDiv === 'OFS') return '개별'
  return null
}

function analysisModeLabel(source) {
  if (!source) return null
  if (source === 'rule') return '규칙 기반'
  if (source === 'groq' || source === 'gemini' || source === 'openai') return 'AI'
  return null
}

function isUserFacingBanner(text) {
  const raw = String(text || '')
  const t = raw.toLowerCase()
  if (!t.trim()) return false
  // AI 폴백 안내는 사용자에게 보여준다
  if (raw.includes('규칙 기반 결과를 표시')) return true
  if (t.includes('gemini') || t.includes('openai') || t.includes('groq')) return false
  if (t.includes('analysis_provider') || t.includes('quota')) return false
  if (t.includes('http 429') || t.includes('resource_exhausted')) return false
  if (t.includes('규칙 기반 분석 사용') || t.includes('rule 폴백')) return false
  return true
}

function growthTone(value) {
  if (value == null || Number.isNaN(Number(value))) return ''
  if (Number(value) > 0) return 'is-up'
  if (Number(value) < 0) return 'is-down'
  return ''
}

export default function CompanyPage() {
  const { companyId } = useParams()
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [data, setData] = useState(null)
  const [trendTab, setTrendTab] = useState('annual')
  const [isFavorite, setIsFavorite] = useState(false)
  const [favBusy, setFavBusy] = useState(false)
  const [favError, setFavError] = useState('')

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setError('')
    setData(null)
    setTrendTab('annual')
    setIsFavorite(false)
    setFavError('')

    getCompanyDashboard(companyId)
      .then((res) => {
        if (cancelled) return
        setData(res)
        setStatus('ok')
        const hasAnnual = (res.trend || []).length > 0
        const hasQuarter = (res.trend_quarterly || []).length > 0
        if (!hasAnnual && hasQuarter) setTrendTab('quarterly')
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'Dashboard를 불러오지 못했습니다.')
        setStatus('error')
      })

    getFavoriteStatus(companyId)
      .then((res) => {
        if (cancelled) return
        setIsFavorite(Boolean(res.is_favorite))
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [companyId])

  const toggleFavorite = async () => {
    if (!companyId || favBusy) return
    setFavBusy(true)
    setFavError('')
    try {
      if (isFavorite) {
        await removeFavorite(companyId)
        setIsFavorite(false)
      } else {
        await addFavorite(companyId)
        setIsFavorite(true)
      }
    } catch (err) {
      setFavError(err.message || '즐겨찾기 변경에 실패했습니다.')
    } finally {
      setFavBusy(false)
    }
  }

  if (status === 'loading') {
    return (
      <section className="page page-wide">
        <p className="back">
          <Link to="/home">← 검색으로</Link>
        </p>
        <div className="skeleton-stack" aria-busy="true" aria-live="polite">
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-card" />
          <div className="skeleton-grid">
            <div className="skeleton skeleton-metric" />
            <div className="skeleton skeleton-metric" />
            <div className="skeleton skeleton-metric" />
            <div className="skeleton skeleton-metric" />
          </div>
        </div>
      </section>
    )
  }

  if (status === 'error') {
    return (
      <section className="page page-wide">
        <p className="back">
          <Link to="/home">← 검색으로</Link>
        </p>
        <h1 className="page-title">기업 분석</h1>
        <div className="banner warn">
          <p>{error}</p>
        </div>
        <Link to="/home" className="btn-secondary" style={{ display: 'inline-block' }}>
          검색으로 돌아가기
        </Link>
      </section>
    )
  }

  const company = data.company
  const indicators = data.indicators
  const growth = data.growth
  const analysis = data.analysis
  const asOf = analysis?.data_as_of || indicators?.period || '-'
  const asOfLabel = formatPeriod(asOf)
  const stmt =
    statementLabel(data.meta?.fs_div || indicators?.fs_div, data.meta?.statement_type) ||
    null

  const annualTrend = data.trend || []
  const quarterlyTrend = data.trend_quarterly || []
  const activeTrend = trendTab === 'quarterly' ? quarterlyTrend : annualTrend
  const periodColLabel = trendTab === 'quarterly' ? '기간' : '연도'

  const analysisMode = analysisModeLabel(data.analysis_source)
  const visibleNotices = (data.notices || []).filter(isUserFacingBanner)
  const visibleWarnings = (data.warnings || []).filter(isUserFacingBanner)

  const revenueGrowth = growth?.revenue_growth ?? indicators?.revenue_growth
  const opGrowth = growth?.operating_income_growth

  return (
    <section className="page page-wide">
      <p className="back">
        <Link to="/home">← 검색으로</Link>
      </p>

      {/* 1. Company Header */}
      <header className="dash-header">
        <div>
          <h1 className="page-title">{company?.company_name || '기업 분석'}</h1>
          <p className="company-meta">
            데이터 기준 {asOfLabel}
            {stmt ? ` · ${stmt} 재무제표` : ''}
          </p>
          <div className="company-meta-row">
            <span className="meta-chip">
              종목 <strong>{company?.stock_code || '-'}</strong>
            </span>
            <span className="meta-chip">
              업종{' '}
              <strong>
                {company?.industry || '미분류'}
                {company?.industry_source === 'groq' ? ' (AI 추정)' : ''}
              </strong>
            </span>
            <span className="meta-chip">
              corp <strong>{company?.corp_code || companyId}</strong>
            </span>
          </div>
        </div>
        <div className="dash-badges">
          <button
            type="button"
            className={`btn-fav ${isFavorite ? 'is-on' : ''}`}
            onClick={toggleFavorite}
            disabled={favBusy}
            title={isFavorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
          >
            {isFavorite ? '★ 즐겨찾기' : '☆ 즐겨찾기'}
          </button>
          {stmt && (
            <span className="badge badge-fs" title="재무제표 기준">
              {stmt}
            </span>
          )}
          {analysisMode && (
            <span className={`badge ${analysisMode === 'AI' ? 'badge-ai' : ''}`}>
              분석: {analysisMode}
            </span>
          )}
          {data.analysis_cached && <span className="badge">캐시</span>}
        </div>
      </header>

      {favError && (
        <div className="banner warn">
          <p>{favError}</p>
        </div>
      )}
      {visibleNotices.length > 0 && (
        <div className="banner info">
          {visibleNotices.map((n) => (
            <p key={n}>{n}</p>
          ))}
        </div>
      )}
      {visibleWarnings.length > 0 && (
        <div className="banner warn">
          {visibleWarnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {/* 2. AI Key Insight */}
      {analysis?.overall_judgment && (
        <section className="insight-card" aria-labelledby="insight-heading">
          <span className="insight-label">AI Key Insight</span>
          <h2 id="insight-heading" className="section-title">
            핵심 요약
          </h2>
          <p className="insight-body">{analysis.overall_judgment}</p>
          {analysis.key_variable && (
            <p className="insight-key">
              <span>핵심 변수</span>
              {analysis.key_variable}
            </p>
          )}
        </section>
      )}

      {/* 3. Key Financial Metrics */}
      <section className="dash-section">
        <div className="section-title-row">
          <h2>주요 재무지표</h2>
          {stmt && <span className="badge badge-fs">{stmt}</span>}
        </div>
        <p className="section-note">
          원본 수치 · 기준 기간 {formatPeriod(indicators?.period)}
          {stmt ? ` · ${stmt} 재무제표` : ''}
        </p>
        {!indicators ? (
          <div className="empty-panel">
            <p>재무지표 데이터가 없습니다.</p>
          </div>
        ) : (
          <div className="metric-grid">
            <Metric
              label="매출"
              value={formatAmount(indicators.revenue)}
              sub={
                revenueGrowth != null
                  ? `성장률 ${formatPercent(revenueGrowth)}`
                  : formatPeriod(indicators.period)
              }
              tone={growthTone(revenueGrowth)}
            />
            <Metric
              label="영업이익"
              value={formatAmount(indicators.operating_income)}
              sub={
                opGrowth != null
                  ? `성장률 ${formatPercent(opGrowth)}`
                  : formatPeriod(indicators.period)
              }
              tone={growthTone(opGrowth)}
            />
            <Metric label="순이익" value={formatAmount(indicators.net_income)} />
            <Metric label="영업CF" value={formatAmount(indicators.operating_cash_flow)} />
            <Metric label="FCF" value={formatAmount(indicators.fcf)} />
            <Metric label="ROE" value={formatPercent(indicators.roe)} />
            <Metric label="ROIC" value={formatPercent(indicators.roic)} />
            <Metric label="영업이익률" value={formatPercent(indicators.operating_margin)} />
            <Metric label="부채비율" value={formatPercent(indicators.debt_ratio)} />
            <Metric label="유동비율" value={formatPercent(indicators.current_ratio)} />
            <Metric label="이자보상배율" value={formatRatio(indicators.interest_coverage)} />
            <Metric
              label="매출 성장률"
              value={formatPercent(revenueGrowth)}
              tone={growthTone(revenueGrowth)}
            />
          </div>
        )}
      </section>

      {/* 4. Financial Trends / Charts */}
      <section className="dash-section">
        <div className="section-title-row">
          <h2>재무 추세</h2>
          {stmt && <span className="badge badge-fs">{stmt}</span>}
        </div>
        <div className="trend-tabs" role="tablist" aria-label="추세 기간">
          <button
            type="button"
            role="tab"
            aria-selected={trendTab === 'annual'}
            className={trendTab === 'annual' ? 'tab active' : 'tab'}
            onClick={() => setTrendTab('annual')}
            disabled={annualTrend.length === 0}
          >
            연간
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={trendTab === 'quarterly'}
            className={trendTab === 'quarterly' ? 'tab active' : 'tab'}
            onClick={() => setTrendTab('quarterly')}
            disabled={quarterlyTrend.length === 0}
          >
            분기
          </button>
        </div>
        <p className="section-note">
          {trendTab === 'annual'
            ? '연간 사업보고서 기준으로 비교합니다.'
            : '분기·반기 보고서 기준으로 비교합니다. 연간 실적과 직접 비교하지 마세요.'}
          {stmt ? ` · ${stmt} 재무제표` : ''}
        </p>
        {activeTrend.length === 0 ? (
          <div className="empty-panel">
            <p>
              {trendTab === 'annual'
                ? '표시할 연간 추세 데이터가 없습니다.'
                : '표시할 분기 추세 데이터가 없습니다.'}
            </p>
          </div>
        ) : (
          <>
            <TrendChart
              trend={activeTrend}
              title={trendTab === 'annual' ? '연간 매출·영업이익 추세' : '분기 매출·영업이익 추세'}
            />
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{periodColLabel}</th>
                    <th>매출</th>
                    <th>영업이익</th>
                    <th>ROE</th>
                    <th>영업이익률</th>
                  </tr>
                </thead>
                <tbody>
                  {activeTrend.map((row) => (
                    <tr key={row.period}>
                      <td>{formatPeriod(row.period)}</td>
                      <td>{formatAmount(row.revenue)}</td>
                      <td>{formatAmount(row.operating_income)}</td>
                      <td>{formatPercent(row.roe)}</td>
                      <td>{formatPercent(row.operating_margin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {/* 5. AI Financial Analysis */}
      <section className="dash-section analysis-section">
        <div className="section-title-row">
          <h2>AI 재무 분석</h2>
          {analysisMode && (
            <span className={`badge ${analysisMode === 'AI' ? 'badge-ai' : ''}`}>
              {analysisMode}
            </span>
          )}
        </div>
        <p className="section-note">
          AI/규칙 기반 해석 · 위 원본 수치와 구분 · 기준일{' '}
          {formatPeriod(analysis?.data_as_of || asOf)}
        </p>
        {!analysis ? (
          <div className="empty-panel">
            <p>분석 결과가 없습니다.</p>
          </div>
        ) : (
          <>
            <div className="analysis-blocks">
              <article>
                <h3 className="card-title">재무 건전성</h3>
                <p>{analysis.financial_soundness}</p>
              </article>
              <article>
                <h3 className="card-title">수익성</h3>
                <p>{analysis.profitability}</p>
              </article>
              <article>
                <h3 className="card-title">성장성</h3>
                <p>{analysis.growth}</p>
              </article>
              <article>
                <h3 className="card-title">이익의 질</h3>
                <p>{analysis.earnings_quality}</p>
              </article>
            </div>

            {/* 6. Strengths / Risks */}
            <div className="sr-grid" style={{ marginTop: 16 }}>
              <div className="sr-card strengths">
                <h3>주요 강점</h3>
                <ul>
                  {(analysis.strengths || []).length === 0 ? (
                    <li>표시할 강점이 없습니다.</li>
                  ) : (
                    (analysis.strengths || []).map((item) => (
                      <li key={item}>{item}</li>
                    ))
                  )}
                </ul>
              </div>
              <div className="sr-card risks">
                <h3>주요 위험요인</h3>
                <ul>
                  {(analysis.risks || []).length === 0 ? (
                    <li>표시할 위험요인이 없습니다.</li>
                  ) : (
                    (analysis.risks || []).map((item) => (
                      <li key={item}>{item}</li>
                    ))
                  )}
                </ul>
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
              <h3 className="card-title">현재 가장 중요한 투자 질문</h3>
              <p className="section-note">
                다음 공시로 검증할 질문입니다. 아래 회색 문구는 답변이 아니라, 지금 이
                질문이 중요한 데이터 근거입니다.
              </p>
              <ol className="question-list">
                {(analysis.key_questions || []).map((item) => (
                  <li key={item.question}>
                    <p className="question-text">{item.question}</p>
                    {item.why && (
                      <p className="question-why">
                        <span className="question-why-label">데이터 근거</span>
                        {item.why}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </div>

            <div style={{ marginTop: 20 }}>
              <h3 className="card-title">앞으로 확인할 데이터</h3>
              <ul>
                {(analysis.data_to_watch || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>

            {analysis.disclaimer && (
              <p className="disclaimer">{analysis.disclaimer}</p>
            )}
          </>
        )}
      </section>

      {/* News placeholder */}
      <section className="dash-section news-section" aria-labelledby="news-heading">
        <div className="section-title-row">
          <h2 id="news-heading">최신 뉴스 분석</h2>
          <span className="badge badge-soon">준비중</span>
        </div>
        <div className="placeholder-box news-coming-soon">
          <p className="news-soon-title">준비중</p>
          <p>조만간 찾아뵙겠습니다ㅎㅎ</p>
          <p className="muted">
            기업 관련 뉴스 요약·감성 분석·원문 링크는 뉴스 API 연동 이후 이 자리에
            표시됩니다.
          </p>
        </div>
      </section>

      {data.industry_profile && (
        <section className="dash-section">
          <h2>업종 참고</h2>
          <p className="section-note">
            {data.industry_profile.industry} · 자본집약도{' '}
            {data.industry_profile.capital_intensity || '-'}
          </p>
          <p className="body-text">{data.industry_profile.profitability_note}</p>
        </section>
      )}
    </section>
  )
}

function Metric({ label, value, sub, tone }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {sub ? <span className={`metric-sub ${tone || ''}`}>{sub}</span> : null}
    </div>
  )
}
