#!/bin/sh

set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] Applying database migrations..."
  alembic upgrade head
  echo "[entrypoint] Migrations completed."
else
  echo "[entrypoint] Skipping database migrations."
fi

exec "$@"
