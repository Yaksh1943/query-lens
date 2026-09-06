import { useEffect, useState } from 'react'
import { runQuery, checkHealth } from './api'
import QueryForm from './components/QueryForm'
import ClarificationCard from './components/ClarificationCard'
import TraceView from './components/TraceView'
import StatsView from './components/StatsView'
import InsightsView from './components/InsightsView'
import ConnectionManager from './components/ConnectionManager'

const NAV_ITEMS = [
  { id: 'query', label: 'query' },
  { id: 'insights', label: 'insights' },
  { id: 'stats', label: 'stats' },
]

function App() {
  const [backendStatus, setBackendStatus] = useState('checking')
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('query')
  const [selectedConnectionId, setSelectedConnectionId] = useState(null)

  useEffect(() => {
    checkHealth()
      .then((ok) => setBackendStatus(ok ? 'connected' : 'error'))
      .catch(() => setBackendStatus('unreachable'))
  }, [])

  async function handleAsk(question) {
    setIsLoading(true)
    setError(null)
    try {
      const data = await runQuery({ question, connectionId: selectedConnectionId })
      setResult(data)
    } catch (err) {
      setError(err.message)
      setResult(null)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleClarify(answer) {
    if (!result?.trace_id) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await runQuery({ traceId: result.trace_id, clarificationAnswer: answer })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <nav
        style={{
          width: '200px',
          flexShrink: 0,
          borderRight: '1px solid var(--border)',
          padding: '1.5rem 1.25rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '2rem',
        }}
      >
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '1.05rem' }}>
            QueryLens
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              marginTop: '0.35rem',
            }}
          >
            {backendStatus}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              style={{
                textAlign: 'left',
                background: 'none',
                border: 'none',
                borderLeft: activeTab === item.id ? '2px solid var(--accent)' : '2px solid transparent',
                color: activeTab === item.id ? 'var(--text)' : 'var(--text-muted)',
                fontFamily: 'var(--font-sans)',
                fontSize: '0.9rem',
                padding: '0.4rem 0 0.4rem 0.75rem',
                cursor: 'pointer',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      <main style={{ flex: 1, padding: '2rem 2.5rem', maxWidth: '760px' }}>
        {activeTab === 'query' && (
          <>
            <ConnectionManager selectedConnectionId={selectedConnectionId} onSelect={setSelectedConnectionId} />
            <QueryForm onSubmit={handleAsk} isLoading={isLoading} />

            {error && (
              <p style={{ color: 'var(--error)', marginTop: '1rem', fontSize: '0.9rem' }}>
                {error}
              </p>
            )}

            {result?.clarification_question && (
              <ClarificationCard
                question={result.clarification_question}
                onSubmit={handleClarify}
                isLoading={isLoading}
              />
            )}

            <TraceView result={result} />
          </>
        )}

        {activeTab === 'stats' && <StatsView />}
        {activeTab === 'insights' && <InsightsView />}
      </main>
    </div>
  )
}

export default App