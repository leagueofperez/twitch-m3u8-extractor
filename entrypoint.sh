#!/bin/sh
set -e

# Usa PORT si está definido, si no, usa 5000
export BIND_PORT="${PORT:-5000}"

# Ejecuta Gunicorn en modo exec (reemplaza el proceso shell)
exec gunicorn \
	--bind "0.0.0.0:${BIND_PORT}" \
	--workers 4 \
	--timeout 60 \
	app:app
