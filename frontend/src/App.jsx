import { useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function App() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/health`)
      .then((res) => res.json())
      .then((data) => setStatus(data.status === 'ok' ? 'connected' : 'error'))
      .catch(() => setStatus('backend unreachable'))
  }, [])

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>QueryLens</h1>
      <p>Backend status: <strong>{status}</strong></p>
      <p>
        This is the Phase 1 scaffold. The natural language query
        interface will be built here next.
      </p>
    </main>
  )
}

export default App
