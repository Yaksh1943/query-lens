import { useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function StatCard({ label, value }) {
  return (
    <div
      style={{
        padding: '1rem',
        background: '#1a1d27',
        border: '1px solid #333',
        borderRadius: '8px',
      }}
    >
      <p style={{ margin: '0 0 0.4rem', fontSize: '0.8rem', color: '#8a92a6', textTransform: 'uppercase' }}>
        {label}
      </p>
      <p style={{ margin: 0, fontSize: '1.5rem', fontWeight: 'bold' }}>{value}</p>
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
      .catch(() => setError('Could not load stats'))
  }, [])

  if (error) {
    return <p style={{ color: '#ff9090' }}>{error}</p>
  }

  if (!stats) {
    return <p style={{ color: '#8a92a6' }}>Loading stats...</p>
  }

  if (stats.total_queries === 0) {
    return <p style={{ color: '#8a92a6' }}>No queries yet — ask something on the Query tab first.</p>
  }

  return (
    <div>
      <p style={{ color: '#8a92a6', fontSize: '0.85rem', marginBottom: '1rem' }}>
        Live usage stats, aggregated from every query this instance has run.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '1rem',
        }}
      >
        <StatCard label="Total queries" value={stats.total_queries} />
        <StatCard label="Success rate" value={`${(stats.success_rate * 100).toFixed(0)}%`} />
        <StatCard label="Ambiguity caught" value={`${(stats.ambiguity_rate * 100).toFixed(0)}%`} />
        <StatCard label="Cache hit rate" value={`${(stats.cache_hit_rate * 100).toFixed(0)}%`} />
        <StatCard label="Avg. execution time" value={`${stats.avg_execution_ms.toFixed(0)} ms`} />
        <StatCard label="Avg. input tokens" value={stats.avg_input_tokens.toFixed(0)} />
        <StatCard label="Avg. output tokens" value={stats.avg_output_tokens.toFixed(0)} />
        <StatCard label="Total tokens used" value={stats.total_tokens_used.toLocaleString()} />
      </div>
    </div>
  )
}

export default StatsView