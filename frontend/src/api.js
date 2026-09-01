const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * Calls POST /api/query.
 *
 * Fresh question:   runQuery({ question: "..." })
 * Follow-up answer: runQuery({ traceId: 4, clarificationAnswer: "..." })
 *
 * Mirrors the backend's QueryRequest shape so components never build
 * fetch bodies themselves.
 */
export async function runQuery({ question, traceId, clarificationAnswer }) {
  const body = traceId != null
    ? { trace_id: traceId, clarification_answer: clarificationAnswer }
    : { question }

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