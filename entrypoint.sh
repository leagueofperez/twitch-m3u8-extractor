#!/bin/sh
set -e

# Usa PORT si está definido, si no, usa 5000
export BIND_PORT="${PORT:-5000}"

# Nº de workers de gunicorn. Cada worker es un proceso con su propia memoria.
export WORKERS="${WORKERS:-4}"

# Ejecuta Gunicorn en modo exec (reemplaza el proceso shell)
exec gunicorn \
	--bind "0.0.0.0:${BIND_PORT}" \
	--workers "$WORKERS" \
	--timeout 60 \
	app:app
