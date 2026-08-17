# Chinook sample database

This project uses [Chinook](https://github.com/lerocha/chinook-database) —
a well-known open sample database modeling a digital music store
(artists, albums, tracks, customers, invoices, employees). It's used as
the "analytics" database the Text-to-SQL engine queries against.

The SQL file itself is **not committed to this repo** (kept out on
purpose to keep the repository lean — it's a generated third-party
asset, not project source). Instead it's fetched automatically by the
setup script.

## To fetch it manually (only needed if the setup script can't reach the internet)

Download the official PostgreSQL script and save it as `init.sql` in
this folder:

- Source: https://github.com/lerocha/chinook-database
- Direct file: https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql
- License: [LICENSE.md](https://github.com/lerocha/chinook-database/blob/master/LICENSE.md) (MIT)

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql" -OutFile "datasets\chinook\init.sql"
```

**macOS / Linux:**
```bash
curl -o datasets/chinook/init.sql https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql
```

This file is loaded automatically into the `chinook` database the
first time the Postgres container starts (via
`infrastructure/docker-compose.yml`'s init-script mount).
