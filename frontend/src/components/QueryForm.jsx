import { useState } from 'react'

function QueryForm({ onSubmit, isLoading }) {
  const [question, setQuestion] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', marginTop: '1.5rem' }}>
      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="ask a question about the data"
        disabled={isLoading}
        style={{
          flex: 1,
          padding: '0.7rem 0.9rem',
          borderRadius: '4px',
          border: '1px solid var(--border)',
          background: 'var(--panel)',
          color: 'var(--text)',
          fontFamily: 'var(--font-sans)',
          fontSize: '0.95rem',
        }}
      />
      <button
        type="submit"
        disabled={isLoading || !question.trim()}
        style={{
          padding: '0.7rem 1.4rem',
          borderRadius: '4px',
          border: 'none',
          background: isLoading ? 'var(--border)' : 'var(--accent)',
          color: isLoading ? 'var(--text-muted)' : 'var(--accent-text)',
          fontFamily: 'var(--font-sans)',
          fontWeight: 600,
          fontSize: '0.95rem',
          cursor: isLoading ? 'default' : 'pointer',
        }}
      >
        {isLoading ? 'thinking' : 'ask'}
      </button>
    </form>
  )
}

export default QueryForm