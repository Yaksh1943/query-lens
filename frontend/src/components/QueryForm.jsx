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
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question about the data..."
        disabled={isLoading}
        style={{
          flex: 1,
          padding: '0.75rem 1rem',
          borderRadius: '6px',
          border: '1px solid #333',
          background: '#1a1d27',
          color: '#e6e6e6',
          fontSize: '1rem',
        }}
      />
      <button
        type="submit"
        disabled={isLoading || !question.trim()}
        style={{
          padding: '0.75rem 1.5rem',
          borderRadius: '6px',
          border: 'none',
          background: isLoading ? '#333' : '#4f6df5',
          color: '#fff',
          fontSize: '1rem',
          cursor: isLoading ? 'default' : 'pointer',
        }}
      >
        {isLoading ? 'Thinking...' : 'Ask'}
      </button>
    </form>
  )
}

export default QueryForm