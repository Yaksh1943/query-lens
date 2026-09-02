import { useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function StatCard({ label, value, sublabel }) {
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
      {sublabel && <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: '#8a92a6' }}>{sublabel}</p>}
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
      .catch(() => setError('Could not load insights'))
  }, [])

  if (error) {
    return <p style={{ color: '#ff9090' }}>{error}</p>
  }

  if (!insights) {
    return <p style={{ color: '#8a92a6' }}>Loading insights...</p>
  }

  if (!insights.available) {
    return (
      <div
        style={{
          padding: '1rem 1.25rem',
          background: '#1a1d27',
          border: '1px solid #333',
          borderRadius: '8px',
          color: '#8a92a6',
        }}
      >
        <p style={{ margin: 0 }}>{insights.message}</p>
      </div>
    )
  }

  const { summary, cases, generated_at } = insights.data
  const ambiguousCases = cases.filter((c) => c.case_type === 'ambiguous')

  return (
    <div>
      <p style={{ color: '#8a92a6', fontSize: '0.85rem', marginBottom: '1rem' }}>
        Evaluation of the ambiguity-detection safety net, comparing behavior with it
        on (real API behavior) vs. off (blind generation). Last run:{' '}
        {new Date(generated_at).toLocaleString()}.
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <StatCard label="Accuracy (check ON)" value={`${(summary.execution_accuracy_on * 100).toFixed(0)}%`} />
        <StatCard label="Accuracy (check OFF)" value={`${(summary.execution_accuracy_off * 100).toFixed(0)}%`} />
        <StatCard label="Ambiguity catch rate" value={`${(summary.ambiguity_catch_rate * 100).toFixed(0)}%`} />
        <StatCard
          label="Token overhead"
          value={`${summary.token_overhead_pct >= 0 ? '+' : ''}${summary.token_overhead_pct.toFixed(0)}%`}
          sublabel="cost of running the safety check"
        />
      </div>

      <h3 style={{ fontSize: '0.85rem', color: '#8a92a6', textTransform: 'uppercase', margin: '0 0 0.5rem' }}>
        Per-question results
      </h3>
      <div style={{ overflowX: 'auto', border: '1px solid #333', borderRadius: '6px', marginBottom: '1.5rem' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.85rem' }}>
          <thead>
            <tr>
              {['Question', 'Type', 'ON pass', 'OFF pass', 'ON tokens', 'OFF tokens'].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: 'left',
                    padding: '0.5rem 0.75rem',
                    background: '#1a1d27',
                    borderBottom: '1px solid #333',
                    color: '#a9b4ff',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.case_id}>
                <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid #22252f' }}>{c.question}</td>
                <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid #22252f' }}>{c.case_type}</td>
                <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid #22252f' }}>
                  {c.on_passed === null ? '—' : c.on_passed ? '✅' : '❌'}
                </td>
                <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid #22252f' }}>
                  {c.off_passed === null ? '—' : c.off_passed ? '✅' : '❌'}
                </td>
                <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid #22252f' }}>
                  {(c.on_input_tokens + c.on_output_tokens).toLocaleString()}
                </td>
                <td style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid #22252f' }}>
                  {(c.off_input_tokens + c.off_output_tokens).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {ambiguousCases.length > 0 && (
        <>
          <h3 style={{ fontSize: '0.85rem', color: '#8a92a6', textTransform: 'uppercase', margin: '0 0 0.5rem' }}>
            What the model generates if the safety check is skipped
          </h3>
          {ambiguousCases.map((c) => (
            <div key={c.case_id} style={{ marginBottom: '1rem' }}>
              <p style={{ margin: '0 0 0.4rem', fontSize: '0.9rem' }}>
                <strong>{c.question}</strong>
              </p>
              <pre
                style={{
                  margin: 0,
                  padding: '0.75rem',
                  background: '#1a1d27',
                  border: '1px solid #333',
                  borderRadius: '6px',
                  overflowX: 'auto',
                  fontSize: '0.8rem',
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