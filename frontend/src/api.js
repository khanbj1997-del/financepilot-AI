// 백엔드(FastAPI) 전용 API 클라이언트.
// 화면은 이 모듈의 함수만 호출한다. 외부 공공·AI API는 여기서 부르지 않는다.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = ''
    try {
      const data = await res.json()
      detail = data.detail || JSON.stringify(data)
    } catch {
      detail = await res.text().catch(() => '')
    }
    throw new Error(typeof detail === 'string' ? detail : `요청 실패 (${res.status})`)
  }
  return res.json()
}

export async function checkHealth() {
  return request('/health')
}

export async function searchCompanies(q, limit = 20) {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return request(`/companies/search?${params}`)
}

export async function getCompanyDashboard(companyId, years = 5, refresh = false) {
  const params = new URLSearchParams({ years: String(years) })
  if (refresh) params.set('refresh', 'true')
  return request(`/companies/${encodeURIComponent(companyId)}/dashboard?${params}`)
}

export async function syncCompanyMaster() {
  return request('/companies/master/sync', { method: 'POST' })
}

export async function listFavorites() {
  return request('/favorites')
}

export async function getFavoriteStatus(companyId) {
  return request(`/favorites/${encodeURIComponent(companyId)}/status`)
}

export async function addFavorite(companyId) {
  return request(`/favorites/${encodeURIComponent(companyId)}`, { method: 'POST' })
}

export async function removeFavorite(companyId) {
  return request(`/favorites/${encodeURIComponent(companyId)}`, { method: 'DELETE' })
}

export async function listThemes(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) })
  return request(`/themes?${params}`)
}

export async function getThemeStocks(themeId, limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) })
  return request(`/themes/${encodeURIComponent(themeId)}/stocks?${params}`)
}

export { BASE_URL }
