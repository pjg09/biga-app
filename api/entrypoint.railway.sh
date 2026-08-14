#!/bin/sh
# Un solo contenedor para los tres procesos del backend (api, worker, beat).
# Railway no deja fijar el start command por servicio desde la CLI, así que el
# rol se elige con la variable PROCESS_TYPE, que sí es CLI-manejable.
set -e

case "${PROCESS_TYPE:-api}" in
  api)
    # Las migraciones corren solo en el proceso web: si las corrieran también
    # worker y beat, tres réplicas competirían por el lock de alembic al
    # desplegar. Railway inyecta PORT; en local no existe.
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    # --concurrency fijo: sin esto Celery mira los núcleos del host de Railway
    # (48) y levanta 48 procesos con una copia entera de la app cada uno, ~1 GB
    # de RAM sin procesar una sola tarea. El límite de CPU del contenedor no lo
    # evita: es un cgroup y os.cpu_count() sigue viendo los 48 del host.
    # Las tareas son envíos de correo (I/O, de a uno): con 2 procesos sobra.
    exec celery -A app.core.celery:celery_app worker --loglevel=info \
      --concurrency=2 --without-gossip --without-mingle
    ;;
  beat)
    # El schedule de beat se guarda en disco. En Railway el filesystem es
    # efímero, así que va a /tmp: se pierde en cada deploy, que es lo correcto
    # para un scheduler sin estado propio.
    exec celery -A app.core.celery:celery_app beat --loglevel=info \
      --schedule /tmp/celerybeat-schedule
    ;;
  *)
    echo "PROCESS_TYPE inválido: '${PROCESS_TYPE}' (api|worker|beat)" >&2
    exit 1
    ;;
esac
