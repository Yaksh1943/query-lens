import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function StatCard({ label, value }) {
  return (
    <div
      style={{
        padding: '0.9rem 1rem',
        background: 'var(--panel)',
        border: '1px solid var(--border)',
        borderRadius: '4px',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.72rem',
          color: 'var(--text-muted)',
          marginBottom: '0.4rem',
        }}
      >
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
    </div>
  )
}

function StatsView() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/stats`)
      .then((res) => res.json())
      .then(setStats)
      .catch(() => setError('could not load stats'))
  }, [])

  if (error) {
    return <p style={{ color: 'var(--error)', fontSize: '0.9rem' }}>{error}</p>
  }

  if (!stats) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>loading</p>
  }

  if (stats.total_queries === 0) {
    return (
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
        no queries yet — ask something on the query tab first
      </p>
    )
  }

  const rateChartData = [
    { name: 'success', value: Math.round(stats.success_rate * 100) },
    { name: 'ambiguity caught', value: Math.round(stats.ambiguity_rate * 100) },
    { name: 'cache hit', value: Math.round(stats.cache_hit_rate * 100) },
  ]

  return (
    <div>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
        live usage, aggregated from every query this instance has run
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '0.75rem',
          marginBottom: '1.75rem',
        }}
      >
        <StatCard label="total queries" value={stats.total_queries} />
        <StatCard label="success rate" value={`${(stats.success_rate * 100).toFixed(0)}%`} />
        <StatCard label="ambiguity caught" value={`${(stats.ambiguity_rate * 100).toFixed(0)}%`} />
        <StatCard label="cache hit rate" value={`${(stats.cache_hit_rate * 100).toFixed(0)}%`} />
        <StatCard label="avg execution" value={`${stats.avg_execution_ms.toFixed(0)}ms`} />
        <StatCard label="avg input tokens" value={stats.avg_input_tokens.toFixed(0)} />
        <StatCard label="avg output tokens" value={stats.avg_output_tokens.toFixed(0)} />
        <StatCard label="total tokens" value={stats.total_tokens_used.toLocaleString()} />
      </div>

      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          marginBottom: '0.5rem',
        }}
      >
        rate comparison
      </div>
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1rem' }}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={rateChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="name"
              tick={{ fill: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-sans)' }}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
              axisLine={{ stroke: 'var(--border)' }}
              unit="%"
            />
            <Tooltip
              contentStyle={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                fontFamily: 'var(--font-sans)',
                fontSize: '0.85rem',
              }}
              formatter={(value) => [`${value}%`, '']}
            />
            <Bar dataKey="value" fill="var(--accent)" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default StatsView