import ClarificationCard from './ClarificationCard'
import TraceView from './TraceView'

function ChatThread({ turns, onClarify }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {turns.map((turn) => (
        <div key={turn.id}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              marginBottom: '0.4rem',
            }}
          >
            you
          </div>
          <p style={{ margin: 0, fontSize: '0.95rem' }}>{turn.question}</p>

          {turn.clarificationAnswer && (
            <div style={{ marginTop: '0.6rem' }}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  color: 'var(--text-muted)',
                  marginBottom: '0.3rem',
                }}
              >
                you answered
              </div>
              <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                {turn.clarificationAnswer}
              </p>
            </div>
          )}

          {turn.isLoading && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>thinking</p>
          )}

          {!turn.isLoading && turn.error && (
            <p style={{ marginTop: '0.75rem', color: 'var(--error)', fontSize: '0.9rem' }}>{turn.error}</p>
          )}

          {!turn.isLoading && turn.result?.clarification_question && !turn.clarificationAnswer && (
            <ClarificationCard
              question={turn.result.clarification_question}
              onSubmit={(answer) => onClarify(turn.id, answer)}
              isLoading={turn.isLoading}
            />
          )}

          {!turn.isLoading && turn.result && (!turn.result.clarification_question || turn.clarificationAnswer) && (
            <TraceView result={turn.result} />
          )}
        </div>
      ))}
    </div>
  )
}

export default ChatThread