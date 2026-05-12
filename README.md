# BIGA APP

Plataforma web mobile-first para el control del PAE y la comunicación colegio–acudiente en instituciones educativas públicas colombianas.

Documentación del proyecto: [`docs/`](docs/)

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

# Verificar jobs registrados en Celery
docker compose logs worker --tail=20

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
  api/          # Backend FastAPI
  web/          # Frontend React + Vite
  docs/         # Documentación de arquitectura, esquema y alcance
  docker-compose.yml
  .env.example
```
