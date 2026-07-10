<#
  One-shot seeder for the KFC hackathon (Windows PowerShell).

  From the project root:
    powershell -ExecutionPolicy Bypass -File scripts\seed.ps1
    powershell -ExecutionPolicy Bypass -File scripts\seed.ps1 -Scrape
    powershell -ExecutionPolicy Bypass -File scripts\seed.ps1 -NoRules
    powershell -ExecutionPolicy Bypass -File scripts\seed.ps1 -Index

  Requires: node + npm, python + pip on PATH. The kfc MONGODB_URI must already
  be in backend\.env and reco\.env (it is, unless you changed them).
#>
param(
  [switch]$Scrape,
  [switch]$NoRules,
  [switch]$Index
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "=== KFC seed ===" -ForegroundColor Cyan
Write-Host "project: $Root"

# 0. sanity
$envFile = Join-Path $Root "backend\.env"
if (-not (Test-Path $envFile)) { throw "backend\.env missing (needs MONGODB_URI)" }
$uriLine = (Select-String -Path $envFile -Pattern "MONGODB_URI").Line
if (-not $uriLine) { throw "MONGODB_URI not set in backend\.env" }
Write-Host ("db -> " + ($uriLine -replace '//[^@]*@','//****@'))

# 1. optional scrape
if ($Scrape) {
  Write-Host "--- scraping live menu ---" -ForegroundColor Yellow
  Push-Location (Join-Path $Root "scraper")
  npm install; npx playwright install chromium; node scrape_menu.js
  Pop-Location
}

# 2. backend install + seed
Write-Host "--- backend: install + seed ---" -ForegroundColor Yellow
Push-Location (Join-Path $Root "backend")
npm install
npm run seed
Pop-Location

# 3. mine rules
if (-not $NoRules) {
  Write-Host "--- reco: install + mine association rules ---" -ForegroundColor Yellow
  Push-Location (Join-Path $Root "reco")
  pip install -q -r requirements.txt
  python -m app.mine_rules
  Pop-Location
}

# 4. optional index
if ($Index) {
  Write-Host "--- reco: build Qdrant index ---" -ForegroundColor Yellow
  Push-Location (Join-Path $Root "reco")
  python -m app.build_index
  Pop-Location
}

Write-Host "=== done. Start backend, then open GET /api/admin/stats to verify ===" -ForegroundColor Green
