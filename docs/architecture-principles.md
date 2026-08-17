# Architecture principles

These are the ground rules this project is built against, carried
over from the original planning phase and adjusted for a solo,
zero-cost, ship-fast build.

1. **Stable contracts, swappable internals.** The rest of the codebase
   depends on interfaces (`LLMProvider`, database session, etc.), never
   on a specific vendor SDK directly. This is what lets the LLM
   provider or database change later without a rewrite.

2. **Deterministic before generative.** Anything that can be enforced
   with code (read-only SQL validation, schema checks) is — the LLM is
   used only where genuine language understanding is required.

3. **Build in vertical slices, not layers.** Each phase in
   `ROADMAP.md` is a complete, demoable capability, not a partial
   layer of every feature. This is a deliberate response to the
   original blueprint's scope being too large to build all at once —
   see the phase breakdown in ROADMAP.md.

4. **No speculative infrastructure.** No microservices, no Kubernetes,
   no vector database, no message queue — none of these are justified
   at this project's scale. They're only added if a real, observed
   need appears, not because they're common in "production" systems.

5. **Observability is structured logs first, dashboards later.**
   Every pipeline stage logs structured data now (Phase 1); the
   analytics/dashboard layer (Phase 4) is built on top of real
   captured data, not designed speculatively ahead of it.

6. **Everything free-tier, chosen deliberately.** Gemini (LLM),
   Postgres via Docker locally / Neon when deployed, Render (backend),
   Vercel (frontend) — each picked for a specific reason documented in
   the README, not defaulted to because they're popular.
