#!/usr/bin/env bash
# Start the API on Render.
#
# Seeding runs here rather than inside the application so that a failure to
# reach the database prints in the deploy log as its own step, and so the
# application itself carries no demo-data code.
set -u

if [ "${SEED_DEMO:-false}" = "true" ]; then
  echo "SEED_DEMO=true: seeding labelled synthetic data if the database is empty"
  # --if-empty does nothing when demo data is already there, so a redeploy
  # neither duplicates it nor wipes real submissions.
  python scripts/seed_demo.py --if-empty || echo "seeding skipped: $?"
fi

exec uvicorn app.main:app \
  --app-dir api \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1
