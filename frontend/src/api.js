const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * Calls POST /api/query.
 *
 * Fresh question:   runQuery({ question: "...", connectionId: 2 })
 * Follow-up answer: runQuery({ traceId: 4, clarificationAnswer: "..." })
 *
 * connectionId is optional — omitting it (or passing null/undefined)
 * queries the default built-in database. Follow-ups don't need it:
 * the backend looks up the original question's connection_id from
 * history automatically.
 */
export async function runQuery({ question, traceId, clarificationAnswer, connectionId }) {
  const body = traceId != null
    ? { trace_id: traceId, clarification_answer: clarificationAnswer }
    : { question, connection_id: connectionId ?? null }

  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail || `Request failed with status ${response.status}`)
  }

  return response.json()
}

export async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`)
  const data = await response.json()
  return data.status === 'ok'
}

export async function listConnections() {
  const response = await fetch(`${API_BASE_URL}/api/connections`)
  return response.json()
}

export async function createConnection({ name, connectionUrl }) {
  const response = await fetch(`${API_BASE_URL}/api/connections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, connection_url: connectionUrl }),
  })

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail || `Request failed with status ${response.status}`)
  }

  return response.json()
}