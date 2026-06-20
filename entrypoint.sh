#!/usr/bin/env bash
# ...existing code...
# Simple entrypoint to switch runtime based on RUN_MODE env var.
# RUN_MODE=api    -> run gunicorn serving buem.apis.api_server:create_app()
# RUN_MODE=worker -> run python -m buem.main
set -e

RUN_MODE="${RUN_MODE:-worker}"   # default to worker if not set
CONDA_ENV="${CONDA_DEFAULT_ENV:-buem_env}"
CONDA_PREFIX="/opt/conda/envs/${CONDA_ENV}"
GUNICORN_BIN="${GUNICORN_BIN:-$CONDA_PREFIX/bin/gunicorn}"
PYTHON_BIN="${PYTHON_BIN:-$CONDA_PREFIX/bin/python}"

# Fallback to 'conda' on PATH if the default path doesn't exist
if [ ! -x "$GUNICORN_BIN" ]; then
  GUNICORN_BIN="$(command -v gunicorn || true)"
fi
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python || true)"
fi

if [ "$RUN_MODE" = "api" ]; then
  if [ -x "$GUNICORN_BIN" ]; then
    exec "$GUNICORN_BIN" --bind 0.0.0.0:5000 "buem.apis.api_server:create_app()" --workers "${GUNICORN_WORKERS:-2}" --threads 1
  else
    # fallback to conda run if binary not found
    exec /opt/conda/bin/conda run -n "$CONDA_ENV" --no-capture-output gunicorn --bind 0.0.0.0:5000 "buem.apis.api_server:create_app()" --workers "${GUNICORN_WORKERS:-2}" --threads 1
  fi
elif [ "$RUN_MODE" = "worker" ]; then
  if [ -x "$PYTHON_BIN" ]; then
    exec "$PYTHON_BIN" -m buem.main
  else
    exec /opt/conda/bin/conda run -n "$CONDA_ENV" --no-capture-output python -m buem.main
  fi
else
  # run arbitrary command passed via docker-compose "command"
  exec "$@"
fi