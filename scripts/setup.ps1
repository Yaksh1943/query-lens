# One-time local setup for Windows (PowerShell).
#
# Usage (from the repo root, in PowerShell):
#   .\scripts\setup.ps1
#
# What it does:
#   1. Copies .env.example -> .env if .env doesn't exist yet.
#   2. Downloads the Chinook sample database SQL (not vendored in the
#      repo — see datasets/chinook/README.md) and prefixes it so it
#      loads into its own database rather than the app database.
#   3. Reminds you of the next command to run.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# 1. .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — open it and add your GEMINI_API_KEY." -ForegroundColor Yellow
} else {
    Write-Host ".env already exists, leaving it as-is." -ForegroundColor Gray
}

# 2. Chinook dataset
$chinookOut = "datasets\chinook\01-chinook-schema.sql"
if (-not (Test-Path $chinookOut)) {
    Write-Host "Downloading Chinook sample database..." -ForegroundColor Cyan
    $url = "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql"
    $raw = Invoke-WebRequest -Uri $url -UseBasicParsing | Select-Object -ExpandProperty Content
    # Prefix with \c so this loads into the `chinook` database created
    # by 00-create-databases.sql, not the default app_db.
    "\c chinook`n$raw" | Set-Content -Path $chinookOut -Encoding utf8
    Write-Host "Saved to $chinookOut" -ForegroundColor Green
} else {
    Write-Host "Chinook dataset already downloaded, skipping." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. Make sure Docker Desktop is running."
Write-Host "  2. Add your Gemini API key to .env if you haven't yet."
Write-Host "  3. Run: docker compose -f infrastructure/docker-compose.yml up --build"
Write-Host "  4. Open http://localhost:5173 (frontend) and http://localhost:8000/docs (API docs)."
