#!/usr/bin/env bash
#
# One-shot seeder for the KFC hackathon (Linux / macOS / Git-Bash / VPS).
# Run from anywhere; it locates the project root relative to this script.
#
#   bash scripts/seed.sh                # menu(sample) + stores + members + vouchers + transactions, then mine rules
#   bash scripts/seed.sh --scrape       # scrape the live KFC menu first
#   bash scripts/seed.sh --no-rules     # skip association-rule mining
#   bash scripts/seed.sh --index        # also build the Qdrant vector index (needs Qdrant running)
#
# Requires: node + npm, python3 + pip. The kfc MONGODB_URI must already be in
# backend/.env and reco/.env (it is, if you haven't changed them).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRAPE=0; RULES=1; INDEX=0
for a in "$@"; do
  case "$a" in
    --scrape) SCRAPE=1 ;;
    --no-rules) RULES=0 ;;
    --index) INDEX=1 ;;
    *) echo "unknown flag: $a"; exit 1 ;;
  esac
done

echo "=== KFC seed ==="
echo "project: $ROOT"

# 0. sanity: env present
[ -f "$ROOT/backend/.env" ] || { echo "!! backend/.env missing (needs MONGODB_URI)"; exit 1; }
grep -q "MONGODB_URI" "$ROOT/backend/.env" || { echo "!! MONGODB_URI not set in backend/.env"; exit 1; }
echo "db → $(grep MONGODB_URI "$ROOT/backend/.env" | sed -E 's#//[^@]*@#//****@#')"

# 1. optional: scrape live menu
if [ "$SCRAPE" = "1" ]; then
  echo "--- scraping live menu ---"
  ( cd "$ROOT/scraper" && npm install --silent && npx playwright install chromium && node scrape_menu.js )
fi

# 2. backend deps + seed
echo "--- backend: install + seed ---"
( cd "$ROOT/backend" && npm install --silent && npm run seed )

# 3. reco deps + mine rules
if [ "$RULES" = "1" ]; then
  echo "--- reco: install + mine association rules ---"
  ( cd "$ROOT/reco" && pip install -q -r requirements.txt && python -m app.mine_rules )
fi

# 4. optional: build vector index
if [ "$INDEX" = "1" ]; then
  echo "--- reco: build Qdrant index ---"
  ( cd "$ROOT/reco" && python -m app.build_index )
fi

echo "=== done. Verify with: (start backend) then GET /api/admin/stats ==="
