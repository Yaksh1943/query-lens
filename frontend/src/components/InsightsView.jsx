import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function StatCard({ label, value, sublabel }) {
  return (
    <div
      style={{
        padding: '0.9rem 1rem',
        background: 'var(--panel)',
        border: '1px solid var(--border)',
        borderRadius: '4px',
      }}
    >
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
        {label}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
      {sublabel && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>{sublabel}</div>
      )}
    </div>
  )
}

function ChartPanel({ title, children }) {
  return (
    <div style={{ marginBottom: '1.75rem' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
        {title}
      </div>
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: '4px', padding: '1rem' }}>
        {children}
      </div>
    </div>
  )
}

function InsightsView() {
  const [insights, setInsights] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/insights`)
      .then((res) => res.json())
      .then(setInsights)
      .catch(() => setError('could not load insights'))
  }, [])

  if (error) {
    return <p style={{ color: 'var(--error)', fontSize: '0.9rem' }}>{error}</p>
  }

  if (!insights) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>loading</p>
  }

  if (!insights.available) {
    return (
      <div
        style={{
          padding: '1rem 1.2rem',
          background: 'var(--panel)',
          border: '1px solid var(--border)',
          borderRadius: '4px',
          color: 'var(--text-muted)',
          fontSize: '0.9rem',
        }}
      >
        {insights.message}
      </div>
    )
  }

  const { summary, cases, generated_at } = insights.data
  const ambiguousCases = cases.filter((c) => c.case_type === 'ambiguous')
  const unambiguousCases = cases.filter((c) => c.case_type === 'unambiguous')

  const tokenChartData = cases.map((c) => ({
    name: c.case_id,
    on: c.on_input_tokens + c.on_output_tokens,
    off: c.off_input_tokens + c.off_output_tokens,
  }))

  const accuracyChartData = unambiguousCases.map((c) => ({
    name: c.case_id,
    on: c.on_passed ? 100 : 0,
    off: c.off_passed ? 100 : 0,
  }))

  const tooltipStyle = {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    fontFamily: 'var(--font-sans)',
    fontSize: '0.85rem',
  }

  const axisTick = { fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }

  return (
    <div>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
        ambiguity-check comparison, on vs off. last run: {new Date(generated_at).toLocaleString()}
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '0.75rem',
          marginBottom: '1.75rem',
        }}
      >
        <StatCard label="accuracy — on" value={`${(summary.execution_accuracy_on * 100).toFixed(0)}%`} />
        <StatCard label="accuracy — off" value={`${(summary.execution_accuracy_off * 100).toFixed(0)}%`} />
        <StatCard label="ambiguity caught" value={`${(summary.ambiguity_catch_rate * 100).toFixed(0)}%`} />
        <StatCard
          label="token overhead"
          value={`${summary.token_overhead_pct >= 0 ? '+' : ''}${summary.token_overhead_pct.toFixed(0)}%`}
          sublabel="cost of the safety check"
        />
      </div>

      {accuracyChartData.length > 0 && (
        <ChartPanel title="accuracy per question — on vs off (unambiguous cases)">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={accuracyChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={axisTick} axisLine={{ stroke: 'var(--border)' }} />
              <YAxis tick={axisTick} axisLine={{ stroke: 'var(--border)' }} unit="%" domain={[0, 100]} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '0.8rem', fontFamily: 'var(--font-sans)' }} />
              <Bar dataKey="on" name="check on" fill="var(--accent)" radius={[2, 2, 0, 0]} />
              <Bar dataKey="off" name="check off" fill="var(--text-muted)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
      )}

      <ChartPanel title="token cost per question — on vs off">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={tokenChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="name" tick={axisTick} axisLine={{ stroke: 'var(--border)' }} />
            <YAxis tick={axisTick} axisLine={{ stroke: 'var(--border)' }} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: '0.8rem', fontFamily: 'var(--font-sans)' }} />
            <Bar dataKey="on" name="check on" fill="var(--accent)" radius={[2, 2, 0, 0]} />
            <Bar dataKey="off" name="check off" fill="var(--text-muted)" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>

      {ambiguousCases.length > 0 && (
        <>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            generated blind, if the check is skipped
          </div>
          {ambiguousCases.map((c) => (
            <div key={c.case_id} style={{ marginBottom: '1rem' }}>
              <p style={{ margin: '0 0 0.4rem', fontSize: '0.9rem' }}>{c.question}</p>
              <pre
                style={{
                  margin: 0,
                  padding: '0.6rem 0.75rem',
                  background: 'var(--panel)',
                  border: '1px solid var(--border)',
                  borderRadius: '4px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.8rem',
                  overflowX: 'auto',
                }}
              >
                {c.off_sql || '(generation failed)'}
              </pre>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

export default InsightsView