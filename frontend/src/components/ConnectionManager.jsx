import { useEffect, useState } from 'react'
import { listConnections, createConnection } from '../api'

function ConnectionManager({ selectedConnectionId, onSelect }) {
  const [connections, setConnections] = useState([])
  const [isAdding, setIsAdding] = useState(false)
  const [name, setName] = useState('')
  const [connectionUrl, setConnectionUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)

  function loadConnections() {
    listConnections()
      .then(setConnections)
      .catch(() => setConnections([]))
  }

  useEffect(() => {
    loadConnections()
  }, [])

  async function handleAdd(e) {
    e.preventDefault()
    if (!name.trim() || !connectionUrl.trim()) return

    setIsSubmitting(true)
    setError(null)
    try {
      const newConnection = await createConnection({ name: name.trim(), connectionUrl: connectionUrl.trim() })
      setName('')
      setConnectionUrl('')
      setIsAdding(false)
      loadConnections()
      onSelect(newConnection.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
        <label style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          database
        </label>
        <select
          value={selectedConnectionId ?? ''}
          onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
          style={{
            padding: '0.35rem 0.5rem',
            borderRadius: '4px',
            border: '1px solid var(--border)',
            background: 'var(--panel)',
            color: 'var(--text)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.85rem',
          }}
        >
          <option value="">default (chinook)</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => setIsAdding(!isAdding)}
          style={{
            padding: '0.35rem 0.65rem',
            borderRadius: '4px',
            border: '1px solid var(--accent)',
            background: 'none',
            color: 'var(--accent)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.8rem',
            cursor: 'pointer',
          }}
        >
          {isAdding ? 'cancel' : '+ add database'}
        </button>
      </div>

      {isAdding && (
        <form
          onSubmit={handleAdd}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
            marginTop: '0.75rem',
            padding: '1rem',
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
          }}
        >
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="name (e.g. my shop db)"
            disabled={isSubmitting}
            style={{
              padding: '0.5rem 0.7rem',
              borderRadius: '4px',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.85rem',
            }}
          />
          <input
            type="text"
            value={connectionUrl}
            onChange={(e) => setConnectionUrl(e.target.value)}
            placeholder="postgresql+psycopg://user:password@host:5432/dbname"
            disabled={isSubmitting}
            style={{
              padding: '0.5rem 0.7rem',
              borderRadius: '4px',
              border: '1px solid var(--border)',
              background: 'var(--bg)',
              color: 'var(--text)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
            }}
          />
          <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            tested before saving · encrypted at rest
          </p>
          {error && <p style={{ margin: 0, color: 'var(--error)', fontSize: '0.82rem' }}>{error}</p>}
          <button
            type="submit"
            disabled={isSubmitting || !name.trim() || !connectionUrl.trim()}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '4px',
              border: 'none',
              background: isSubmitting ? 'var(--border)' : 'var(--accent)',
              color: isSubmitting ? 'var(--text-muted)' : 'var(--accent-text)',
              fontFamily: 'var(--font-sans)',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: isSubmitting ? 'default' : 'pointer',
            }}
          >
            {isSubmitting ? 'testing connection' : 'add database'}
          </button>
        </form>
      )}
    </div>
  )
}

export default ConnectionManager