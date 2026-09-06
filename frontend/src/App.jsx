import { useState } from 'react'
import { runQuery, checkHealth } from './api'
import { useEffect } from 'react'
import QueryForm from './components/QueryForm'
import ChatThread from './components/ChatThread'
import StatsView from './components/StatsView'
import InsightsView from './components/InsightsView'
import ConnectionManager from './components/ConnectionManager'

const NAV_ITEMS = [
  { id: 'query', label: 'query' },
  { id: 'insights', label: 'insights' },
  { id: 'stats', label: 'stats' },
]

let nextTurnId = 1

function App() {
  const [backendStatus, setBackendStatus] = useState('checking')
  const [turns, setTurns] = useState([])
  const [activeTab, setActiveTab] = useState('query')
  const [selectedConnectionId, setSelectedConnectionId] = useState(null)

  useEffect(() => {
    checkHealth()
      .then((ok) => setBackendStatus(ok ? 'connected' : 'error'))
      .catch(() => setBackendStatus('unreachable'))
  }, [])

  function updateTurn(id, patch) {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)))
  }

  async function handleAsk(question) {
    const id = nextTurnId++
    setTurns((prev) => [
      ...prev,
      { id, question, clarificationAnswer: null, result: null, isLoading: true, error: null },
    ])

    try {
      const data = await runQuery({ question, connectionId: selectedConnectionId })
      updateTurn(id, { result: data, isLoading: false })
    } catch (err) {
      updateTurn(id, { error: err.message, isLoading: false })
    }
  }

  async function handleClarify(turnId, answer) {
    const turn = turns.find((t) => t.id === turnId)
    if (!turn?.result?.trace_id) return

    updateTurn(turnId, { isLoading: true })
    try {
      const data = await runQuery({ traceId: turn.result.trace_id, clarificationAnswer: answer })
      updateTurn(turnId, { result: data, clarificationAnswer: answer, isLoading: false })
    } catch (err) {
      updateTurn(turnId, { error: err.message, isLoading: false })
    }
  }

  const isAnyLoading = turns.some((t) => t.isLoading)

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

      <main style={{ flex: 1, padding: '2rem 2.5rem', maxWidth: '760px', display: 'flex', flexDirection: 'column' }}>
        {activeTab === 'query' && (
          <>
            <ConnectionManager selectedConnectionId={selectedConnectionId} onSelect={setSelectedConnectionId} />

            {turns.length > 0 && (
              <div style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
                <ChatThread turns={turns} onClarify={handleClarify} />
              </div>
            )}

            <div style={{ marginTop: turns.length === 0 ? '1.5rem' : 0 }}>
              <QueryForm onSubmit={handleAsk} isLoading={isAnyLoading} />
            </div>
          </>
        )}

        {activeTab === 'stats' && <StatsView />}
        {activeTab === 'insights' && <InsightsView />}
      </main>
    </div>
  )
}

export default App