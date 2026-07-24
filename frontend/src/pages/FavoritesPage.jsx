import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listFavorites, removeFavorite } from '../api'

export default function FavoritesPage() {
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [items, setItems] = useState([])
  const [removingId, setRemovingId] = useState(null)
  const [actionError, setActionError] = useState('')

  const load = () => {
    setStatus('loading')
    setError('')
    setActionError('')
    listFavorites()
      .then((res) => {
        const list = res.items || []
        setItems(list)
        setStatus(list.length === 0 ? 'empty' : 'ok')
      })
      .catch((err) => {
        setError(err.message || '즐겨찾기 목록을 불러오지 못했습니다.')
        setStatus('error')
      })
  }

  useEffect(() => {
    load()
  }, [])

  const onRemove = async (companyId, e) => {
    e.preventDefault()
    e.stopPropagation()
    setRemovingId(companyId)
    setActionError('')
    try {
      await removeFavorite(companyId)
      setItems((prev) => {
        const next = prev.filter((it) => it.company_id !== companyId)
        setStatus(next.length === 0 ? 'empty' : 'ok')
        return next
      })
    } catch (err) {
      setActionError(err.message || '즐겨찾기 제거에 실패했습니다.')
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <section className="page">
      <h1 className="page-title">즐겨찾기</h1>
      <p className="lead">관심 기업을 한곳에서 관리하고, 바로 분석 Dashboard로 이동하세요.</p>

      {status === 'loading' && (
        <div className="skeleton-stack" aria-busy="true">
          <div className="skeleton skeleton-card" />
          <div className="skeleton skeleton-card" />
        </div>
      )}

      {status === 'error' && (
        <div className="banner warn">
          <p>{error}</p>
          <button type="button" className="btn-secondary" onClick={load}>
            다시 시도
          </button>
        </div>
      )}

      {actionError && (
        <div className="banner warn">
          <p>{actionError}</p>
        </div>
      )}

      {status === 'empty' && (
        <div className="empty-panel">
          <p>아직 즐겨찾기한 기업이 없습니다.</p>
          <p className="muted">
            기업 분석 화면에서 ☆ 즐겨찾기를 누르면 여기에 추가됩니다.{' '}
            <Link to="/home">검색으로 이동</Link>
          </p>
        </div>
      )}

      {status === 'ok' && (
        <ul className="fav-grid">
          {items.map((item) => {
            const company = item.company
            const name = company?.company_name || item.company_id
            const meta = [
              company?.stock_code || '-',
              company?.industry || '업종 미분류',
            ].join(' · ')
            return (
              <li key={item.company_id}>
                <div className="fav-card">
                  <Link
                    to={`/companies/${item.company_id}`}
                    className="fav-card-link"
                  >
                    <span className="result-name">{name}</span>
                    <span className="result-meta">{meta}</span>
                  </Link>
                  <button
                    type="button"
                    className="btn-fav-remove"
                    disabled={removingId === item.company_id}
                    onClick={(e) => onRemove(item.company_id, e)}
                    title="즐겨찾기 해제"
                  >
                    {removingId === item.company_id ? '…' : '★ 해제'}
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
