#!/bin/sh
# Container entrypoint for a hosted deployment (Render and friends).
#
# Migrations run on every boot: a hosted database starts empty, and nothing
# else in this repo would ever create the schema there. `alembic upgrade
# head` is idempotent, so a restart with no new revisions is a no-op.
#
# SEED_DEMO_DATA=true additionally loads the demo accounts, so an evaluator
# can sign in and see populated screens. The seeds are idempotent and only
# ever touch their own fixed user ids; registration stays open either way.
set -e

echo "==> alembic upgrade head"
alembic upgrade head

if [ "$SEED_DEMO_DATA" = "true" ]; then
  echo "==> seeding demo data"
  # One account that exercises every feature, rather than the three
  # feature-specific ones the local scripts still create.
  python -m scripts.seed_demo
  python -m scripts.seed_catalog
fi

echo "==> starting uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
