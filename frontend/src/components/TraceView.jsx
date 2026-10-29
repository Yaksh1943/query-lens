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
        padding: '1rem',
        background: 'var(--panel)',
        border: '1px solid var(--border)',
        borderRadius: '6px',
      }}
    >
      {title && (
        <div
          style={{
            fontSize: '0.78rem',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
            marginBottom: '0.8rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={{ fontWeight: 600, color: 'var(--text)' }}>{title}</span>
          <span style={{ fontSize: '0.7rem', color: '#4ade80', background: 'rgba(74, 222, 128, 0.1)', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>
            ● Auto-inferred {type.toUpperCase()}
          </span>
        </div>
      )}

      <div style={{ width: '100%', height: 260 }}>
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
                outerRadius={85}
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
  const { sql, success, result: queryResult, answer, errors, clarification_question, chart_recommendation, retrieved_tables, self_corrected } = result

  // Default to chart view if a recommendation exists, else table
  const [activeTab, setActiveTab] = useState(chart_recommendation ? 'chart' : 'table')
  const [showSqlTrace, setShowSqlTrace] = useState(false)
  const [copied, setCopied] = useState(false)

  if (clarification_question) return null

  // Error view
  if (!success) {
    return (
      <div style={{ marginTop: '1.25rem', padding: '1rem', background: 'var(--panel)', border: '1px solid var(--error)', borderRadius: '6px' }}>
        <div style={{ color: 'var(--error)', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', fontFamily: 'var(--font-mono)' }}>
          Execution Failed
        </div>
        <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--error)', fontSize: '0.85rem' }}>
          {(errors || []).map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
        {sql && (
          <pre
            style={{
              marginTop: '0.75rem',
              padding: '0.6rem 0.75rem',
              background: 'var(--bg)',
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
      </div>
    )
  }

  function handleCopySql() {
    if (!sql) return
    navigator.clipboard.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* 1. Direct Answer Card (Primary Focus) */}
      {answer && (
        <div
          style={{
            padding: '1.1rem 1.25rem',
            background: 'var(--panel)',
            borderLeft: '3px solid var(--accent)',
            borderRadius: '0 6px 6px 0',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '0.5rem',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              Answer
            </span>

            {/* Status Pills */}
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {self_corrected && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontFamily: 'var(--font-mono)',
                    padding: '0.15rem 0.45rem',
                    borderRadius: '4px',
                    background: 'rgba(56, 189, 248, 0.15)',
                    color: '#38bdf8',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                  }}
                >
                  ⚡ Self-Healed
                </span>
              )}
              {retrieved_tables && retrieved_tables.length > 0 && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontFamily: 'var(--font-mono)',
                    padding: '0.15rem 0.45rem',
                    borderRadius: '4px',
                    background: 'rgba(168, 85, 247, 0.15)',
                    color: '#c084fc',
                    border: '1px solid rgba(168, 85, 247, 0.3)',
                  }}
                >
                  🔍 RAG Scoped: {retrieved_tables.slice(0, 3).join(', ')}
                  {retrieved_tables.length > 3 ? ` +${retrieved_tables.length - 3}` : ''}
                </span>
              )}
            </div>
          </div>
          <p style={{ margin: 0, fontSize: '1rem', lineHeight: '1.55', whiteSpace: 'pre-wrap' }}>{answer}</p>
        </div>
      )}

      {/* 2. Visual Data Section (Tabs: Chart vs Table) */}
      {queryResult && queryResult.rows && queryResult.rows.length > 0 && (
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
          {/* Header Bar with Toggle Controls */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '0.6rem 0.9rem',
              borderBottom: '1px solid var(--border)',
              background: 'var(--panel-alt)',
            }}
          >
            <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              Data Output ({queryResult.row_count} row{queryResult.row_count === 1 ? '' : 's'})
            </span>

            {/* View Switcher Pills */}
            <div style={{ display: 'flex', gap: '0.25rem', background: 'var(--panel)', padding: '0.15rem', borderRadius: '5px', border: '1px solid var(--border)' }}>
              {chart_recommendation && (
                <button
                  type="button"
                  onClick={() => setActiveTab('chart')}
                  style={{
                    border: 'none',
                    background: activeTab === 'chart' ? 'var(--accent)' : 'transparent',
                    color: activeTab === 'chart' ? 'var(--accent-text)' : 'var(--text-muted)',
                    fontSize: '0.75rem',
                    padding: '0.25rem 0.65rem',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: activeTab === 'chart' ? 600 : 400,
                    transition: 'all 0.15s ease',
                  }}
                >
                  📊 Chart
                </button>
              )}
              <button
                type="button"
                onClick={() => setActiveTab('table')}
                style={{
                  border: 'none',
                  background: activeTab === 'table' ? 'var(--accent)' : 'transparent',
                  color: activeTab === 'table' ? 'var(--accent-text)' : 'var(--text-muted)',
                  fontSize: '0.75rem',
                  padding: '0.25rem 0.65rem',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: activeTab === 'table' ? 600 : 400,
                  transition: 'all 0.15s ease',
                }}
              >
                📄 Table
              </button>
            </div>
          </div>

          {/* Content Body */}
          <div style={{ padding: '0.85rem' }}>
            {activeTab === 'chart' && chart_recommendation ? (
              <InteractiveChart recommendation={chart_recommendation} rows={queryResult.rows} />
            ) : (
              <div style={{ overflowX: 'auto', maxHeight: '360px' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.83rem' }}>
                  <thead>
                    <tr>
                      {queryResult.columns.map((col) => (
                        <th
                          key={col}
                          style={{
                            textAlign: 'left',
                            padding: '0.45rem 0.65rem',
                            borderBottom: '1px solid var(--border)',
                            color: 'var(--text-muted)',
                            fontWeight: 600,
                            fontFamily: 'var(--font-mono)',
                            fontSize: '0.75rem',
                            position: 'sticky',
                            top: 0,
                            background: 'var(--panel)',
                          }}
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {queryResult.rows.map((row, i) => (
                      <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255, 255, 255, 0.02)' }}>
                        {queryResult.columns.map((col) => (
                          <td
                            key={col}
                            style={{
                              padding: '0.45rem 0.65rem',
                              borderBottom: '1px solid var(--border)',
                              fontFamily: typeof row[col] === 'number' ? 'var(--font-mono)' : 'inherit',
                            }}
                          >
                            {String(row[col] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. Collapsible SQL & Reasoning Trace (Engineering Details) */}
      <div style={{ border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
        <button
          type="button"
          onClick={() => setShowSqlTrace(!showSqlTrace)}
          style={{
            width: '100%',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0.55rem 0.85rem',
            background: 'var(--panel)',
            border: 'none',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span>
            {showSqlTrace ? '▼ Hide SQL & Reasoning Trace' : '▶ View Generated SQL & Reasoning Trace'}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {showSqlTrace ? 'Collapse' : 'Expand'}
          </span>
        </button>

        {showSqlTrace && (
          <div style={{ padding: '0.85rem', background: 'var(--bg)', borderTop: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                PostgreSQL (Executed with auto-LIMIT & AST Security)
              </span>
              <button
                type="button"
                onClick={handleCopySql}
                style={{
                  background: 'var(--panel)',
                  border: '1px solid var(--border)',
                  color: copied ? '#4ade80' : 'var(--text-muted)',
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  padding: '0.15rem 0.5rem',
                  borderRadius: '3px',
                  cursor: 'pointer',
                }}
              >
                {copied ? '✓ Copied' : 'Copy SQL'}
              </button>
            </div>
            <pre
              style={{
                margin: 0,
                padding: '0.75rem',
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                overflowX: 'auto',
                color: 'var(--text)',
                lineHeight: 1.4,
              }}
            >
              {sql}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

export default TraceView
