# BIGA APP

Plataforma web mobile-first para el control del PAE y la comunicación colegio–acudiente en instituciones educativas públicas colombianas.

Documentación del proyecto: [`docs/`](docs/) — empezar por [`docs/README.md`](docs/README.md).

**Módulos:** asistencia clase a clase con aviso al acudiente y justificación por enlace ·
PAE (inscripción, entrega con doble hash encadenado, auditoría, aviso de no reclamo) ·
convivencia con firma · salidas anticipadas · estudiantes y acudientes ·
consola de administración (personal, académico, horarios, inscritos al PAE, estadísticas) ·
landing pública con solicitud de demo.

**Despliegue:** Railway. Un push a `main` **no** aplica migraciones por sí mismo — las corre el
contenedor al arrancar. Ver [`docs/deployment.md`](docs/deployment.md) antes de desplegar.

---

## Requisitos

- Docker y Docker Compose
- Node.js 22+ (solo si vas a correr el frontend fuera de Docker)
- Python 3.12+ (solo si vas a correr la API fuera de Docker)

---

## Levantar el entorno de desarrollo

```bash
cp .env.example .env
docker compose up -d
```

Verificar que todo esté sano:

```bash
docker compose ps
```

Todos los servicios deben mostrar `Up`. `postgres` y `redis` deben mostrar `(healthy)`.

---

## Servicios y puertos

| Servicio | URL / Puerto | Descripción |
|---|---|---|
| API (FastAPI) | `http://localhost:8000` | Backend. Docs en `/docs` |
| Frontend (React) | `http://localhost:5173` | Vite dev server |
| PostgreSQL | `localhost:5433` | Puerto 5433 — ver nota abajo |
| Redis | `localhost:6379` | Broker de Celery |
| MinIO (storage) | `http://localhost:9001` | Consola web: `minioadmin / minioadmin` |

> **Nota sobre PostgreSQL:** el contenedor expone el puerto `5433` en el host (no `5432`) porque la máquina de desarrollo tiene una instancia local de PostgreSQL corriendo en ese puerto. Cualquier cliente externo (TablePlus, DBeaver, psql) debe conectarse al `5433`.

---

## Comandos frecuentes

```bash
# Ver logs en tiempo real
docker compose logs -f api
docker compose logs -f worker

# Tareas registradas en Celery (esto sí las lista; los logs solo muestran actividad)
docker compose exec -T worker celery -A app.core.celery:celery_app inspect registered

# Recargar el worker tras cambiar código en api/app/jobs/ (no tiene autoreload)
docker compose exec worker python -c "import os, signal; os.kill(1, signal.SIGHUP)"

# Correr migraciones
docker compose exec api alembic upgrade head

# Generar nueva migración
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Bajar el stack
docker compose down

# Bajar y borrar volúmenes (destruye BD y storage)
docker compose down -v
```

---

## Estructura del repositorio

```
biga/
  api/          # Backend FastAPI (app/, alembic/, scripts/, tests/)
  web/          # Frontend React + Vite
  docs/         # Documentación: índice en docs/README.md
  infra/        # Imágenes auxiliares (init del bucket de MinIO)
  scripts/      # Seeds SQL que se pipean con psql (los de Python viven en api/scripts/)
  docker-compose.yml
  .env.example
```

Los `CLAUDE.md` de la raíz y de `web/` contienen las reglas de trabajo del repo (arquitectura,
invariantes y gotchas); se cargan solos al trabajar con Claude Code y se leen igual de bien a mano.
