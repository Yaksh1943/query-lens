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
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <label style={{ fontSize: '0.85rem', color: '#8a92a6' }}>Database:</label>
        <select
          value={selectedConnectionId ?? ''}
          onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
          style={{
            padding: '0.4rem 0.6rem',
            borderRadius: '6px',
            border: '1px solid #333',
            background: '#1a1d27',
            color: '#e6e6e6',
            fontSize: '0.9rem',
          }}
        >
          <option value="">Default (Chinook)</option>
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          onClick={() => setIsAdding(!isAdding)}
          style={{
            padding: '0.4rem 0.75rem',
            borderRadius: '6px',
            border: '1px solid #4f6df5',
            background: 'transparent',
            color: '#a9b4ff',
            fontSize: '0.85rem',
            cursor: 'pointer',
          }}
        >
          {isAdding ? 'Cancel' : '+ Add database'}
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
            background: '#1a1d27',
            border: '1px solid #333',
            borderRadius: '8px',
          }}
        >
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name (e.g. My Shop DB)"
            disabled={isSubmitting}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid #333',
              background: '#0f1117',
              color: '#e6e6e6',
              fontSize: '0.9rem',
            }}
          />
          <input
            type="text"
            value={connectionUrl}
            onChange={(e) => setConnectionUrl(e.target.value)}
            placeholder="postgresql+psycopg://user:password@host:5432/dbname"
            disabled={isSubmitting}
            style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid #333',
              background: '#0f1117',
              color: '#e6e6e6',
              fontSize: '0.9rem',
            }}
          />
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#8a92a6' }}>
            The connection is tested before saving, and the connection string is encrypted at rest.
          </p>
          {error && <p style={{ margin: 0, color: '#ff9090', fontSize: '0.85rem' }}>{error}</p>}
          <button
            type="submit"
            disabled={isSubmitting || !name.trim() || !connectionUrl.trim()}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: '6px',
              border: 'none',
              background: isSubmitting ? '#333' : '#4f6df5',
              color: '#fff',
              fontSize: '0.9rem',
              cursor: isSubmitting ? 'default' : 'pointer',
            }}
          >
            {isSubmitting ? 'Testing connection...' : 'Add database'}
          </button>
        </form>
      )}
    </div>
  )
}

export default ConnectionManager