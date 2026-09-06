function TraceRow({ number, label, children }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: '1rem',
        padding: '0.85rem 0',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
          width: '1.2rem',
          flexShrink: 0,
        }}
      >
        {number}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            marginBottom: '0.35rem',
          }}
        >
          {label}
        </div>
        {children}
      </div>
    </div>
  )
}

function TraceView({ result }) {
  if (!result) return null

  const { sql, success, result: queryResult, answer, errors, clarification_question } = result

  if (clarification_question) return null

  if (!success) {
    return (
      <div style={{ marginTop: '1.5rem' }}>
        <TraceRow number="!" label="failed">
          <ul style={{ margin: 0, paddingLeft: '1.1rem', color: 'var(--error)', fontSize: '0.9rem' }}>
            {(errors || []).map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
          {sql && (
            <pre
              style={{
                marginTop: '0.6rem',
                padding: '0.6rem 0.75rem',
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                overflowX: 'auto',
              }}
            >
              {sql}
            </pre>
          )}
        </TraceRow>
      </div>
    )
  }

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <TraceRow number="1" label="sql">
        <pre
          style={{
            margin: 0,
            padding: '0.6rem 0.75rem',
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            overflowX: 'auto',
          }}
        >
          {sql}
        </pre>
      </TraceRow>

      {queryResult && queryResult.rows && queryResult.rows.length > 0 && (
        <TraceRow number="2" label={`result — ${queryResult.row_count} row${queryResult.row_count === 1 ? '' : 's'}`}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.85rem' }}>
              <thead>
                <tr>
                  {queryResult.columns.map((col) => (
                    <th
                      key={col}
                      style={{
                        textAlign: 'left',
                        padding: '0.4rem 0.6rem',
                        borderBottom: '1px solid var(--border)',
                        color: 'var(--text-muted)',
                        fontWeight: 500,
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.78rem',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queryResult.rows.map((row, i) => (
                  <tr key={i}>
                    {queryResult.columns.map((col) => (
                      <td
                        key={col}
                        style={{
                          padding: '0.4rem 0.6rem',
                          borderBottom: '1px solid var(--border)',
                        }}
                      >
                        {String(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TraceRow>
      )}

      {answer && (
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
              marginBottom: '0.4rem',
            }}
          >
            answer
          </div>
          <p style={{ margin: 0, fontSize: '1rem', whiteSpace: 'pre-wrap' }}>{answer}</p>
        </div>
      )}
    </div>
  )
}

export default TraceView