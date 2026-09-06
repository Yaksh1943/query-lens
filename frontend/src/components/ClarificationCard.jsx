import { useState } from 'react'

function ClarificationCard({ question, onSubmit, isLoading }) {
  const [answer, setAnswer] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = answer.trim()
    if (!trimmed || isLoading) return
    onSubmit(trimmed)
  }

  return (
    <div
      style={{
        marginTop: '1rem',
        padding: '1rem 1.2rem',
        background: 'var(--panel)',
        borderLeft: '2px solid var(--accent)',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          marginBottom: '0.5rem',
        }}
      >
        needs clarification
      </div>
      <p style={{ margin: '0 0 0.75rem', fontSize: '0.95rem' }}>{question}</p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="your answer"
          disabled={isLoading}
          style={{
            flex: 1,
            padding: '0.55rem 0.8rem',
            borderRadius: '4px',
            border: '1px solid var(--border)',
            background: 'var(--bg)',
            color: 'var(--text)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.9rem',
          }}
        />
        <button
          type="submit"
          disabled={isLoading || !answer.trim()}
          style={{
            padding: '0.55rem 1.1rem',
            borderRadius: '4px',
            border: 'none',
            background: isLoading ? 'var(--border)' : 'var(--accent)',
            color: isLoading ? 'var(--text-muted)' : 'var(--accent-text)',
            fontFamily: 'var(--font-sans)',
            fontWeight: 600,
            fontSize: '0.9rem',
            cursor: isLoading ? 'default' : 'pointer',
          }}
        >
          submit
        </button>
      </form>
    </div>
  )
}

export default ClarificationCard