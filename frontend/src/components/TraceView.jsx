function TraceView({ result }) {
  if (!result) return null

  const { sql, success, result: queryResult, answer, errors, clarification_question } = result

  // Clarification is handled by a separate component (ClarificationCard) - don't render here.
  if (clarification_question) return null

  if (!success) {
    return (
      <div
        style={{
          border: '1px solid #e5484d',
          borderRadius: '8px',
          padding: '1rem 1.25rem',
          background: '#1a1d27',
          marginTop: '1rem',
        }}
      >
        <p style={{ margin: 0, color: '#ff9090', fontWeight: 'bold' }}>Query failed</p>
        <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.25rem', color: '#ffb3b3' }}>
          {(errors || []).map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
        {sql && (
          <pre
            style={{
              marginTop: '0.75rem',
              padding: '0.75rem',
              background: '#0f1117',
              borderRadius: '6px',
              overflowX: 'auto',
              fontSize: '0.85rem',
            }}
          >
            {sql}
          </pre>
        )}
      </div>
    )
  }

  return (
    <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <section>
        <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#8a92a6', textTransform: 'uppercase' }}>
          Generated SQL
        </h3>
        <pre
          style={{
            margin: 0,
            padding: '0.75rem',
            background: '#1a1d27',
            border: '1px solid #333',
            borderRadius: '6px',
            overflowX: 'auto',
            fontSize: '0.85rem',
          }}
        >
          {sql}
        </pre>
      </section>

      {queryResult && queryResult.rows && queryResult.rows.length > 0 && (
        <section>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#8a92a6', textTransform: 'uppercase' }}>
            Result ({queryResult.row_count} row{queryResult.row_count === 1 ? '' : 's'})
          </h3>
          <div style={{ overflowX: 'auto', border: '1px solid #333', borderRadius: '6px' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.9rem' }}>
              <thead>
                <tr>
                  {queryResult.columns.map((col) => (
                    <th
                      key={col}
                      style={{
                        textAlign: 'left',
                        padding: '0.5rem 0.75rem',
                        background: '#1a1d27',
                        borderBottom: '1px solid #333',
                        color: '#a9b4ff',
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
                          padding: '0.5rem 0.75rem',
                          borderBottom: '1px solid #22252f',
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
        </section>
      )}

      {answer && (
        <section
          style={{
            padding: '1rem 1.25rem',
            background: '#161a2e',
            border: '1px solid #4f6df5',
            borderRadius: '8px',
          }}
        >
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: '#a9b4ff', textTransform: 'uppercase' }}>
            Answer
          </h3>
          <p style={{ margin: 0, fontSize: '1rem', whiteSpace: 'pre-wrap' }}>{answer}</p>
        </section>
      )}
    </div>
  )
}

export default TraceView