#!/usr/bin/env bash
# One-time local setup for macOS/Linux.
#
# Usage (from the repo root):
#   chmod +x scripts/setup.sh && ./scripts/setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 1. .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — open it and add your GEMINI_API_KEY."
else
    echo ".env already exists, leaving it as-is."
fi

# 2. Chinook dataset
CHINOOK_OUT="datasets/chinook/01-chinook-schema.sql"
if [ ! -f "$CHINOOK_OUT" ]; then
    echo "Downloading Chinook sample database..."
    URL="https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql"
    {
        echo '\c chinook'
        curl -fsSL "$URL"
    } > "$CHINOOK_OUT"
    echo "Saved to $CHINOOK_OUT"
else
    echo "Chinook dataset already downloaded, skipping."
fi

echo ""
echo "Setup complete. Next steps:"
echo "  1. Make sure Docker is running."
echo "  2. Add your Gemini API key to .env if you haven't yet."
echo "  3. Run: docker compose -f infrastructure/docker-compose.yml up --build"
echo "  4. Open http://localhost:5173 (frontend) and http://localhost:8000/docs (API docs)."
