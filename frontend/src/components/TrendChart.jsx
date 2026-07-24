import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatAmount, formatPeriod } from '../utils/format'

export default function TrendChart({ trend, title = '매출·영업이익 추세' }) {
  const data = [...(trend || [])]
    .slice()
    .reverse()
    .map((row) => ({
      period: formatPeriod(row.period),
      revenue: row.revenue,
      operating_income: row.operating_income,
    }))

  if (!data.length) {
    return <p className="state">추세 데이터가 없습니다.</p>
  }

  return (
    <div className="chart-panel">
      <div className="chart-head">
        <h3 className="chart-title">{title}</h3>
        <span className="chart-unit">단위: 원 (차트 축은 조·억 축약)</span>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="period" tick={{ fontSize: 12, fill: '#6b7280' }} />
            <YAxis
              tick={{ fontSize: 11, fill: '#6b7280' }}
              width={72}
              tickFormatter={(v) => {
                const n = Number(v)
                if (Math.abs(n) >= 1e12) return `${(n / 1e12).toFixed(0)}조`
                if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(0)}억`
                return String(v)
              }}
            />
            <Tooltip
              formatter={(value, name) => [
                formatAmount(value),
                name === 'revenue' ? '매출' : '영업이익',
              ]}
            />
            <Legend
              formatter={(value) => (value === 'revenue' ? '매출' : '영업이익')}
            />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#0b1f3a"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="operating_income"
              stroke="#1d4ed8"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
