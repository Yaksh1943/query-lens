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
        border: '1px solid #4f6df5',
        borderRadius: '8px',
        padding: '1rem 1.25rem',
        background: '#1a1d27',
        marginTop: '1rem',
      }}
    >
      <p style={{ margin: '0 0 0.75rem', color: '#a9b4ff' }}>
        Needs clarification: <strong>{question}</strong>
      </p>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Your answer..."
          disabled={isLoading}
          style={{
            flex: 1,
            padding: '0.6rem 0.9rem',
            borderRadius: '6px',
            border: '1px solid #333',
            background: '#0f1117',
            color: '#e6e6e6',
            fontSize: '0.95rem',
          }}
        />
        <button
          type="submit"
          disabled={isLoading || !answer.trim()}
          style={{
            padding: '0.6rem 1.25rem',
            borderRadius: '6px',
            border: 'none',
            background: isLoading ? '#333' : '#4f6df5',
            color: '#fff',
            fontSize: '0.95rem',
            cursor: isLoading ? 'default' : 'pointer',
          }}
        >
          Submit
        </button>
      </form>
    </div>
  )
}

export default ClarificationCard