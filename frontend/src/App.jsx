import { useEffect, useState } from 'react'
import { runQuery, checkHealth } from './api'
import QueryForm from './components/QueryForm'
import ClarificationCard from './components/ClarificationCard'
import TraceView from './components/TraceView'
import StatsView from './components/StatsView'

function App() {
  const [backendStatus, setBackendStatus] = useState('checking...')
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('query')

  useEffect(() => {
    checkHealth()
      .then((ok) => setBackendStatus(ok ? 'connected' : 'error'))
      .catch(() => setBackendStatus('backend unreachable'))
  }, [])

  async function handleAsk(question) {
    setIsLoading(true)
    setError(null)
    try {
      const data = await runQuery({ question })
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
    <main style={{ fontFamily: 'sans-serif', padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.25rem' }}>QueryLens</h1>
      <p style={{ margin: '0 0 1.5rem', fontSize: '0.85rem', color: '#8a92a6' }}>
        Backend: <strong>{backendStatus}</strong>
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <button
          onClick={() => setActiveTab('query')}
          style={{
            padding: '0.5rem 1rem',
            borderRadius: '6px',
            border: 'none',
            background: activeTab === 'query' ? '#4f6df5' : '#1a1d27',
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          Query
        </button>
        <button
          onClick={() => setActiveTab('stats')}
          style={{
            padding: '0.5rem 1rem',
            borderRadius: '6px',
            border: 'none',
            background: activeTab === 'stats' ? '#4f6df5' : '#1a1d27',
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          Stats
        </button>
      </div>

      {activeTab === 'query' && (
        <>
          <QueryForm onSubmit={handleAsk} isLoading={isLoading} />

          {error && (
            <p style={{ color: '#ff9090', marginTop: '1rem' }}>
              Something went wrong: {error}
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
    </main>
  )
}

export default App