#!/bin/sh
set -e

API_PORT="${PORT:-9000}"
CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9001}"
BUCKET="${STORAGE_BUCKET_NAME:-biga}"

# El bucket se crea contra el server ya levantado, así que minio arranca
# primero en background y el mc espera a que responda. `mb --ignore-existing`
# lo hace idempotente entre reinicios.
minio server /data --address ":${API_PORT}" --console-address ":${CONSOLE_PORT}" &
MINIO_PID=$!

until mc alias set local "http://127.0.0.1:${API_PORT}" \
  "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null 2>&1; do
  sleep 1
done
mc mb --ignore-existing "local/${BUCKET}"

wait "${MINIO_PID}"
