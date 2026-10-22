# Roadmap

This project is built in phases on purpose — each phase is a working,
demoable increment, not a partial feature. See `docs/blueprint.md` for
the full architectural reasoning behind these decisions.

## Phase 1 — Core pipeline (Completed)
The essential Text-to-SQL flow, end to end:
- [x] Repo scaffold: FastAPI + React + Docker Compose, health check wired
- [x] Schema introspection (read the Chinook schema into a structured form)
- [x] Schema-aware prompt construction
- [x] SQL generation via Gemini + Groq/Ollama fallbacks
- [x] SQL validation (read-only enforcement, AST syntax check via sqlglot)
- [x] Safe execution against the target database
- [x] Result formatting + natural-language answer
- [x] Query history (list + trace detail view)
- [x] Minimal React UI: ask a question, see SQL + result + explanation

## Phase 2 — Clarification & Agentic RAG (Completed)
- [x] Ambiguity detection on the incoming question
- [x] Clarifying-question UX when the question is underspecified
- [x] Bounded self-correction reflection loop when generated SQL fails validation/execution
- [x] Local CPU Embedding Engine (`fastembed` with `bge-small-en-v1.5`, 0 API cost)
- [x] Semantic Query Caching with cosine similarity thresholding (instant ~15ms hits, 0 tokens)
- [x] Hybrid Schema Retrieval (Dense Vector + Sparse Keyword RRF + FlashRank cross-encoder)
- [x] Few-Shot Golden Query RAG injection
- [x] Modular Agent State Machine (`RouterAgent`, `RetrievalAgent`, `SQLAgent`, `GuardAgent`, `HealingAgent`, `InsightAgent`)
- [x] Auto-inferred interactive chart visualizations (Bar, Line, Pie) rendered in React via Recharts

## Phase 3 — Evaluation
- [ ] Small curated benchmark (subset of Spider/BIRD, sized to stay within free LLM rate limits)
- [ ] Baseline vs. intelligent-pipeline comparison harness
- [ ] Evaluation results view

## Phase 4 — Analytics
- [ ] Aggregate dashboards over the structured logs captured since Phase 1
  (latency percentiles, cost estimates, query success rate)
