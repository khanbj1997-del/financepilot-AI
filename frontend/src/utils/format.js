/** 금액/비율/기간 표시용 헬퍼 (내부 계산값과 분리, 표시 전용) */

function asNumber(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'string') {
    const text = value.trim().replace(/,/g, '').replace(/%/g, '')
    if (!text || text === '-' || text === '데이터 없음') return null
    if (/[경조억만]원/.test(value) || (value.includes('원') && /[^\d.\-]/.test(value))) {
      return null // 이미 포맷된 문자열
    }
    const n = Number(text)
    return Number.isNaN(n) ? null : n
  }
  const n = Number(value)
  return Number.isNaN(n) ? null : n
}

function trimDecimals(numStr) {
  if (!numStr.includes('.')) return numStr
  return numStr.replace(/\.?0+$/, '')
}

function formatScaled(value, divisor, unit) {
  const scaled = Math.round((value / divisor) * 100) / 100
  const sign = scaled < 0 ? '-' : ''
  const abs = Math.abs(scaled)
  let body = abs.toLocaleString('ko-KR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  body = trimDecimals(body)
  return `${sign}${body}${unit}`
}

/**
 * 큰 금액을 경/조/억/만 단위로 표시.
 * @example formatFinancialAmount(23147103000000) → "23.15조원"
 */
export function formatFinancialAmount(value) {
  if (typeof value === 'string') {
    const t = value.trim()
    if (/[경조억만]원/.test(t) && /\d/.test(t)) return t
  }
  const n = asNumber(value)
  if (n === null) return '-'
  if (n === 0) return '0원'

  const abs = Math.abs(n)
  if (abs >= 1e16) return formatScaled(n, 1e16, '경원')
  if (abs >= 1e12) return formatScaled(n, 1e12, '조원')
  if (abs >= 1e8) return formatScaled(n, 1e8, '억원')
  if (abs >= 1e4) return formatScaled(n, 1e4, '만원')
  return `${Math.round(n).toLocaleString('ko-KR')}원`
}

/** @deprecated 이름 호환 — formatFinancialAmount와 동일 */
export function formatAmount(value) {
  return formatFinancialAmount(value)
}

/** 비율은 항상 % 포함. 이미 %가 있으면 중복하지 않음. */
export function formatPercent(value) {
  if (typeof value === 'string' && value.trim().endsWith('%')) {
    const inner = value.trim().slice(0, -1).replace(/,/g, '')
    const n = Number(inner)
    if (!Number.isNaN(n)) return `${n.toFixed(2)}%`
    return value.trim()
  }
  const n = asNumber(value)
  if (n === null) return '-'
  return `${n.toFixed(2)}%`
}

export function formatRatio(value) {
  const n = asNumber(value)
  if (n === null) return '-'
  return `${n.toFixed(2)}배`
}

/** 2025Q3 → 2025 3분기, 2025H1 → 2025 반기, 2025 → 2025 연간 */
export function formatPeriod(period) {
  if (!period) return '-'
  const text = String(period).toUpperCase()
  const m = text.match(/^(\d{4})(Q1|H1|Q3)?$/)
  if (!m) return String(period)
  const year = m[1]
  const tag = m[2]
  if (tag === 'Q1') return `${year} 1분기`
  if (tag === 'H1') return `${year} 반기`
  if (tag === 'Q3') return `${year} 3분기`
  return `${year} 연간`
}
