# QueryLens

Ask a database a question in plain English and get back the generated
SQL, the result, and a natural-language answer — with the full
reasoning trace visible, not a black box.

## Why this project

Most Text-to-SQL demos hide the reasoning: you ask a question, you get
an answer, and you have no way to tell whether the SQL was correct or
the model just got lucky. QueryLens treats the pipeline as something
to be *observed*: every question shows its generated SQL, is validated
before it's ever allowed to run (read-only, schema-checked), and is
logged with enough detail to reconstruct exactly what happened —
including whether the question was ambiguous, whether it was served
from cache, and how many tokens it cost.

## How it works

1. Check cache (exact match on question + database)
2. If a cache miss: check ambiguity and generate SQL in one combined LLM call
3. Validate the SQL (single `SELECT` only, known tables/columns, auto-`LIMIT`)
4. Execute against the target database
5. Generate a natural-language answer from the real result rows
6. Save the full trace to history

If a question is ambiguous ("who are the top customers?" — by what
measure?), the pipeline stops before generating SQL and asks a
clarifying question instead of guessing. The user's answer is merged
with the original question and re-run through the pipeline.

Repeated identical questions are served from an exact-match SQL cache:
the ambiguity check and SQL generation are skipped, but the query is
still re-executed fresh and the answer regenerated, so a cache hit can
never return stale data — only the LLM calls that don't need to change
are skipped. Measured effect: roughly 92% fewer tokens and 70% lower
latency on a cache hit (see `eval/report.md` once generated).

For databases with many tables, a cheap first LLM call narrows down to
the tables actually relevant to a question before the real generation
prompt includes their full column detail — this keeps token cost
bounded as schema size grows, instead of dumping every table into
every prompt. Below roughly 20 tables (including the bundled Chinook
dataset) this step is skipped entirely, since it would add cost with
no benefit at that size.

## Multi-database support

QueryLens isn't hardcoded to one database. You can add any
Postgres-compatible connection through the UI; its credentials are
encrypted at rest (Fernet symmetric encryption) and only ever
referenced by an internal ID afterward — the raw connection string is
never returned by the API once saved. Each connection gets its own
schema cache and its own query cache.

## Tech stack, and why

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | Async-friendly, typed, auto-generated OpenAPI docs |
| LLM | Google Gemini (free tier) | Strong free-tier model for SQL generation, behind a provider interface so it can be swapped |
| Database | PostgreSQL, local install | No cloud dependency to run this project; Alembic manages schema migrations |
| Frontend | React + Vite | Pure client app talking to a separate API — no SSR/routing complexity needed |
| Charts | Recharts | Stats and eval comparisons rendered as real charts, not just numbers |
| Encryption | `cryptography` (Fernet) | Encrypts stored database connection strings at rest |
| SQL parsing | `sqlglot` | AST-based validation instead of regex — catches destructive statements, unknown tables/columns |
| CI | GitHub Actions | Lint and tests on every push |

Sample data: [Chinook](https://github.com/lerocha/chinook-database), a
digital music store schema, used as the default database being
queried.

## Setup

**Prerequisites:** Python 3.12+, Node.js 20+, a local PostgreSQL
instance, and a free Gemini API key from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create `backend/.env` (not the repo root) with:

```
APP_DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/app_db
ANALYTICS_DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/chinook
GEMINI_API_KEY=<your key>
ENCRYPTION_KEY=<generate one, see below>
```

Generate a real encryption key (used to encrypt stored database
connection strings):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create the two databases, load the Chinook sample data into `chinook`
(see `datasets/chinook/`), then apply migrations and start the server:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000 (interactive docs at `/docs`)
- Health check: http://127.0.0.1:8000/api/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173. Set `VITE_API_BASE_URL` if the backend
isn't on the default `http://localhost:8000`.

## Running tests

```bash
cd backend
pytest -v
```

## Evaluation

`eval/run_eval.py` measures the ambiguity check's real impact: it runs
a labeled question set through the pipeline twice — once with the
check active, once bypassed — and compares execution accuracy and
token cost. The AI generates the SQL and answers being measured; the
pass/fail scoring, token totals, and accuracy percentages are computed
by plain code comparing results against hand-written expected answers,
not by asking the model to grade itself.

```bash
cd backend
python -m eval.run_eval
```

This makes real API calls (roughly 35–40 for the full 15-case set) and
is throttled to stay under Gemini's free-tier rate limit, so it takes
several minutes. It writes `eval/report.md` (human-readable) and
`eval/report.json`, which the frontend's Insights tab renders live via
`GET /api/insights`. If you haven't run it yet, the Insights tab says
so plainly rather than showing stale or fabricated numbers.

## Known limitations, and why

Stated plainly rather than left implicit:

- **No authentication.** Anyone with API access can add database
  connections or view history. Deferred deliberately — this is a
  single-user portfolio project, not a multi-tenant product; adding
  auth now would be scope without a real user to protect against.
- **Exact-match caching only, not semantic.** "Top 5 customers" and
  "first five customers" are different cache entries. Semantic
  caching (e.g. via GPTCache or embeddings) would catch these too, but
  needs a vector store — a deliberate line this project doesn't cross.
- **Per-question latency is dominated by free-tier rate limiting, not
  model inference time.** Every LLM call is throttled to stay under 5
  requests/minute; a paid tier would remove this bottleneck without
  any code changes.
- **No high-concurrency handling** (queuing, horizontal scaling,
  connection pooling beyond SQLAlchemy's default). Not built because
  there's no real concurrent load to handle yet — the honest move here
  is designing for the load that exists, not the load that might exist
  someday.
- **Connection strings are encrypted at rest, but engines are cached
  in-process** — a restart clears the engine cache (reconnecting on
  next use is transparent, just slightly slower).

## Project structure

```
query-lens/
├── backend/
│   ├── app/
│   │   ├── api/routes/      HTTP routes (query, stats, insights, connections, health)
│   │   ├── core/            prompts, SQL generation/validation, ambiguity, caching, schema selection, crypto
│   │   ├── llm/             LLM provider abstraction (Gemini, swappable)
│   │   ├── db/              session, schema introspection, connection management, models
│   │   └── observability/   structured logging
│   ├── alembic/              schema migrations
│   ├── eval/                 evaluation harness and labeled test cases
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/       query thread, trace view, stats/insights charts, connection manager
│       └── theme.css          design tokens (dark/light, adapts to OS setting)
└── datasets/chinook/          sample database
```

## License

MIT — see [`LICENSE`](LICENSE).