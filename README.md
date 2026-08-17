# QueryLens

Ask questions about a database in plain English and get back the SQL
query, the result, and a natural-language explanation — with the full
reasoning trace visible, not a black box.

> **Status:** Phase 1 (core pipeline) in progress. See
> [`docs/ROADMAP.md`](docs/ROADMAP.md) for what's built and what's
> next. This project is deliberately built in staged, working
> increments rather than all at once — see
> [`docs/architecture-principles.md`](docs/architecture-principles.md)
> for why.

<!--
  TODO: Add a screenshot or GIF of the Ask flow here once the UI
  exists — question in, SQL + result + explanation out. This is the
  single highest-value thing in this README for anyone skimming it.
-->

## Why this project

Most Text-to-SQL demos hide the reasoning: you ask a question, you get
an answer, and you have no way to tell whether the SQL was correct or
whether the model just got lucky. This project treats the query
pipeline as something to be *observed*, not trusted blindly — every
question shows its generated SQL, is validated before it's allowed to
run (read-only, schema-checked), and is logged with enough detail to
reconstruct exactly what happened.

## Tech stack, and why

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI (Python) | Async-friendly, typed, auto-generated OpenAPI docs |
| LLM | Google Gemini (free tier) | Strongest free-tier model available for SQL generation quality, behind a provider interface so it can be swapped |
| Database | PostgreSQL (Docker locally) | Industry-standard RDBMS; running it in Docker means zero setup cost and zero cloud dependency to run this project locally |
| Frontend | React + Vite | This is a pure client app talking to a separate API — no SSR/routing complexity needed, so a lighter build than Next.js |
| Containerization | Docker Compose | One command brings up the whole stack — see Quickstart |
| CI | GitHub Actions | Free for public repos; runs tests + lint on every push |

Sample data: [Chinook](https://github.com/lerocha/chinook-database) —
a digital music store schema (artists, albums, tracks, customers,
invoices) — used as the database being queried. See
[`datasets/chinook/README.md`](datasets/chinook/README.md).

## Quickstart (Docker — recommended)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

```powershell
git clone https://github.com/<your-username>/query-lens.git
cd query-lens

# Windows (PowerShell)
.\scripts\setup.ps1

# macOS / Linux
# chmod +x scripts/setup.sh && ./scripts/setup.sh
```

Open `.env` and add a free Gemini API key from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey), then:

```powershell
docker compose -f infrastructure/docker-compose.yml up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000 (interactive docs at `/docs`)
- Health check: http://localhost:8000/api/health

First startup takes a minute — Postgres is loading the Chinook sample
data. Subsequent starts are fast.

To stop: `Ctrl+C`, then `docker compose -f infrastructure/docker-compose.yml down`
(add `-v` to also wipe the database and start fresh next time).

## Manual setup (without Docker)

Only needed if you can't run Docker. You'll need Python 3.11+,
Node.js 20+, and a local PostgreSQL 16 instance.

<details>
<summary>Backend</summary>

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
# Set APP_DATABASE_URL and ANALYTICS_DATABASE_URL env vars to point at
# your local Postgres instance (see app/core/config.py for the format).
uvicorn app.main:app --reload
```
</details>

<details>
<summary>Frontend</summary>

```powershell
cd frontend
npm install
npm run dev
```
</details>

<details>
<summary>Database</summary>

Create two databases in your local Postgres instance (`app_db` and
`chinook`), then run `datasets/chinook/00-create-databases.sql`
followed by the fetched `01-chinook-schema.sql` (see
`datasets/chinook/README.md`) against them.
</details>

## Running tests

```powershell
cd backend
pytest -v
```

## Project structure

```
query-lens/
├── backend/            FastAPI app
│   ├── app/
│   │   ├── api/        HTTP routes only
│   │   ├── core/        config
│   │   ├── llm/          LLM provider abstraction
│   │   ├── db/            database session/engine
│   │   └── observability/  structured logging
│   └── tests/
├── frontend/           React + Vite app
├── datasets/chinook/    sample database setup
├── infrastructure/      docker-compose.yml
├── docs/                 roadmap + architecture notes
└── scripts/              one-command local setup
```

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full phased plan
(core pipeline → clarification → evaluation → analytics) and
[`docs/architecture-principles.md`](docs/architecture-principles.md)
for the reasoning behind the scope and tech choices.

## License

MIT — see [`LICENSE`](LICENSE).
