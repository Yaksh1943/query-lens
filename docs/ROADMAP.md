# Roadmap

This project is built in phases on purpose — each phase is a working,
demoable increment, not a partial feature. See `docs/blueprint.md` for
the full architectural reasoning behind these decisions.

## Phase 1 — Core pipeline (in progress)
The essential Text-to-SQL flow, end to end:
- [x] Repo scaffold: FastAPI + React + Docker Compose, health check wired
- [ ] Schema introspection (read the Chinook schema into a structured form)
- [ ] Schema-aware prompt construction
- [ ] SQL generation via Gemini
- [ ] SQL validation (read-only enforcement, syntax check)
- [ ] Safe execution against the Chinook database
- [ ] Result formatting + natural-language answer
- [ ] Query history (list + trace detail view)
- [ ] Minimal React UI: ask a question, see SQL + result + explanation

## Phase 2 — Clarification
- [ ] Ambiguity detection on the incoming question
- [ ] Clarifying-question UX when the question is underspecified
- [ ] Bounded self-correction when generated SQL fails validation/execution

## Phase 3 — Evaluation
- [ ] Small curated benchmark (subset of Spider/BIRD, sized to stay within free LLM rate limits)
- [ ] Baseline vs. intelligent-pipeline comparison harness
- [ ] Evaluation results view

## Phase 4 — Analytics
- [ ] Aggregate dashboards over the structured logs captured since Phase 1
  (latency percentiles, cost estimates, query success rate)

## Deployment (planned, not yet built)
- Backend: Render (free tier)
- App database: Neon (free tier, scale-to-zero)
- Frontend: Vercel (free tier)

This is documented now so it's an explicit decision, not an
afterthought — but isn't wired up until the phases above are further
along, per current priorities.
