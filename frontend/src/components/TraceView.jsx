import { useState } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

const CHART_PALETTE = ['#4FB6A8', '#D4A24C', '#38BDF8', '#A855F7', '#F43F5E', '#10B981', '#F59E0B']

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

function InteractiveChart({ recommendation, rows }) {
  if (!recommendation || !rows || rows.length < 2) return null

  const { type, x_key, y_key, name_key, value_key, title } = recommendation

  const chartData = rows.map((r) => {
    const item = { ...r }
    if (y_key && item[y_key] != null) {
      const num = Number(item[y_key])
      if (!isNaN(num)) item[y_key] = num
    }
    if (value_key && item[value_key] != null) {
      const num = Number(item[value_key])
      if (!isNaN(num)) item[value_key] = num
    }
    return item
  })

  return (
    <div
      style={{
        marginTop: '0.75rem',
        padding: '0.85rem 1rem',
        background: 'var(--panel)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
      }}
    >
      {title && (
        <div
          style={{
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            marginBottom: '0.6rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>{title}</span>
          <span style={{ fontSize: '0.7rem', color: '#4ade80' }}>● Auto-inferred by InsightAgent</span>
        </div>
      )}

      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          {type === 'line' ? (
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey={x_key} stroke="var(--text-muted)" fontSize={11} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} />
              <Tooltip
                contentStyle={{
                  background: 'var(--panel)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                  fontSize: '0.8rem',
                  borderRadius: '4px',
                }}
              />
              <Line type="monotone" dataKey={y_key} stroke="#D4A24C" strokeWidth={2.5} dot={{ fill: '#D4A24C', r: 3 }} />
            </LineChart>
          ) : type === 'pie' ? (
            <PieChart>
              <Tooltip
                contentStyle={{
                  background: 'var(--panel)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                  fontSize: '0.8rem',
                  borderRadius: '4px',
                }}
              />
              <Pie
                data={chartData}
                dataKey={value_key || y_key}
                nameKey={name_key || x_key}
                cx="50%"
                cy="50%"
                outerRadius={80}
                stroke="var(--panel)"
                strokeWidth={2}
              >
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={CHART_PALETTE[index % CHART_PALETTE.length]} />
                ))}
              </Pie>
            </PieChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey={x_key} stroke="var(--text-muted)" fontSize={11} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} />
              <Tooltip
                contentStyle={{
                  background: 'var(--panel)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                  fontSize: '0.8rem',
                  borderRadius: '4px',
                }}
              />
              <Bar dataKey={y_key} fill="#4FB6A8" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function TraceView({ result }) {
  const [viewMode, setViewMode] = useState('both') // 'both', 'chart', 'table'

  if (!result) return null

  const { sql, success, result: queryResult, answer, errors, clarification_question, chart_recommendation } = result

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
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.45rem' }}>
          {result.self_corrected && (
            <div
              style={{
                display: 'inline-block',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
                background: 'rgba(56, 189, 248, 0.15)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}
            >
              ⚡ Auto-corrected via self-healing loop
            </div>
          )}
          {result.retrieved_tables && result.retrieved_tables.length > 0 && (
            <div
              style={{
                display: 'inline-block',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
                background: 'rgba(168, 85, 247, 0.15)',
                color: '#c084fc',
                border: '1px solid rgba(168, 85, 247, 0.3)',
              }}
            >
              🔍 RAG Scoped Schema: {result.retrieved_tables.join(', ')}
            </div>
          )}
          {chart_recommendation && (
            <div
              style={{
                display: 'inline-block',
                padding: '0.2rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
                background: 'rgba(34, 197, 94, 0.15)',
                color: '#4ade80',
                border: '1px solid rgba(34, 197, 94, 0.3)',
              }}
            >
              📊 Recommended: {chart_recommendation.type.toUpperCase()} Chart ({chart_recommendation.title || chart_recommendation.y_key})
            </div>
          )}
        </div>
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
        <TraceRow
          number="2"
          label={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{`result — ${queryResult.row_count} row${queryResult.row_count === 1 ? '' : 's'}`}</span>
              {chart_recommendation && (
                <div style={{ display: 'flex', gap: '0.3rem', fontSize: '0.72rem' }}>
                  <button
                    type="button"
                    onClick={() => setViewMode('both')}
                    style={{
                      background: viewMode === 'both' ? 'var(--panel)' : 'transparent',
                      border: '1px solid var(--border)',
                      color: viewMode === 'both' ? 'var(--text)' : 'var(--text-muted)',
                      borderRadius: '3px',
                      padding: '0.15rem 0.4rem',
                      cursor: 'pointer',
                    }}
                  >
                    All
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('chart')}
                    style={{
                      background: viewMode === 'chart' ? 'var(--panel)' : 'transparent',
                      border: '1px solid var(--border)',
                      color: viewMode === 'chart' ? 'var(--text)' : 'var(--text-muted)',
                      borderRadius: '3px',
                      padding: '0.15rem 0.4rem',
                      cursor: 'pointer',
                    }}
                  >
                    Chart
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('table')}
                    style={{
                      background: viewMode === 'table' ? 'var(--panel)' : 'transparent',
                      border: '1px solid var(--border)',
                      color: viewMode === 'table' ? 'var(--text)' : 'var(--text-muted)',
                      borderRadius: '3px',
                      padding: '0.15rem 0.4rem',
                      cursor: 'pointer',
                    }}
                  >
                    Table
                  </button>
                </div>
              )}
            </div>
          }
        >
          {/* Chart View */}
          {chart_recommendation && (viewMode === 'both' || viewMode === 'chart') && (
            <InteractiveChart recommendation={chart_recommendation} rows={queryResult.rows} />
          )}

          {/* Table View */}
          {(viewMode === 'both' || viewMode === 'table' || !chart_recommendation) && (
            <div style={{ overflowX: 'auto', marginTop: chart_recommendation && viewMode === 'both' ? '0.85rem' : 0 }}>
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
          )}
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