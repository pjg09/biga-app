# BIGA — Decisiones de Arquitectura

> Documento de referencia para el equipo de desarrollo.  
> Refleja las decisiones técnicas tomadas para el MVP. Toda desviación debe discutirse y registrarse aquí.

---

## 1. Estilo arquitectural

**Monolito por capas** — no microservicios, no DDD, no Clean Architecture.

El dominio de BIGA en su fase MVP es straightforward: registrar eventos escolares y enviar notificaciones. No existe lógica de negocio suficientemente compleja ni volumen de tráfico que justifique la sobrecarga operativa y cognitiva de microservicios o los patrones de indirección de DDD y Clean Architecture.

La arquitectura elegida entrega el mismo nivel de testabilidad y separación de responsabilidades sin el boilerplate innecesario.

### Capas del backend

```
HTTP Request
     │
     ▼
┌─────────────┐
│   Router    │  Recibe la request HTTP. Valida entrada con Pydantic.
│             │  No contiene lógica de negocio. Delega al Service.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Service   │  Contiene toda la lógica de negocio.
│             │  Orquesta llamadas al Repository y a servicios externos.
│             │  No sabe nada de HTTP ni de SQL.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Repository  │  Único punto de acceso a la base de datos.
│             │  Habla SQLAlchemy. No contiene lógica de negocio.
└──────┬──────┘
       │
       ▼
  PostgreSQL
```

**Regla estricta**: ninguna capa puede saltarse la inmediatamente siguiente. Un Router nunca toca el Repository directamente.

---

## 2. Estructura de carpetas

```
biga-api/
  app/
    routers/            # Endpoints HTTP organizados por módulo
      pae.py
      attendance.py
      agendatorio.py
      departures.py
      auth.py
      imports.py        # Carga masiva desde Excel
    services/           # Lógica de negocio
      pae_service.py
      attendance_service.py
      agendatorio_service.py
      departure_service.py
      notification_service.py
      import_service.py
    repositories/       # Acceso a base de datos
      student_repository.py
      pae_repository.py
      attendance_repository.py
      agendatorio_repository.py
      departure_repository.py
    schemas/            # Pydantic: modelos de entrada y salida
      pae.py
      attendance.py
      agendatorio.py
      departures.py
      imports.py
    models/             # SQLAlchemy ORM
      institution.py
      student.py
      guardian.py
      user.py
      pae.py
      attendance.py
      agendatorio.py
      departure.py
    jobs/               # Tareas Celery
      pae_jobs.py
      attendance_jobs.py
      departure_jobs.py
    adapters/           # Implementaciones de servicios externos
      email/
        base.py         # Protocol (interfaz)
        resend.py
        ses.py
      storage/
        base.py         # Protocol (interfaz)
        s3.py           # Compatible con MinIO y AWS S3
    core/
      config.py         # Settings desde variables de entorno
      security.py       # JWT, generación de tokens de justificación
      database.py       # Engine y sesión SQLAlchemy
      celery.py         # Configuración Celery
  tests/
    unit/
    integration/

biga-web/               # Frontend React
  src/
    pages/
    components/
    hooks/
    services/           # HTTP client hacia la API
```

---

## 3. Componentes de infraestructura

| Componente | Tecnología | Justificación |
|---|---|---|
| Base de datos | PostgreSQL | Definido en stack |
| API | FastAPI + Pydantic v2 | Definido en stack |
| Frontend | React + Vite | Reemplaza Preact |
| ORM | SQLAlchemy 2.x async + Alembic | Estándar Python, migraciones controladas |
| Jobs asíncronos | Celery 5.x | Reintentos, dead-letter queue, visibilidad |
| Broker de jobs | Redis | Ligero, portable, compatible con Celery |
| Storage | MinIO (dev) / S3-compatible (prod) | Intercambiable vía variable de entorno |
| Email | Resend | SDK Python limpio, fácil de reemplazar |
| Contenedores | Docker + Docker Compose | Portabilidad ante deploy indefinido |

### Docker Compose (servicios)

```
api       → FastAPI
worker    → Celery worker
beat      → Celery beat (scheduler de jobs periódicos)
postgres  → PostgreSQL
redis     → Redis
minio     → Object storage local
```

### Jobs programados

| Job | Trigger | Descripción |
|---|---|---|
| `notify_absent_first_hour` | Inmediato al guardar ausencia en primera hora | Notifica al acudiente e incluye enlace único de justificación |
| `notify_pae_no_claim` | Cron al cierre del horario PAE | Notifica acudientes de estudiantes PAE que no reclamaron |
| `notify_early_departure` | Inmediato al registrar salida temprana | Notifica al acudiente |
| `notify_discipline_record` | Inmediato al guardar registro agendatorio | Notifica al acudiente |

---

## 4. Base de datos — Diseño multi-tenant

Todas las tablas operativas incluyen `institution_id` desde el inicio, aunque el MVP arranque con una sola institución. Retrofitear multi-tenancy sobre un esquema plano tiene un costo muy alto.

### Entidades núcleo

```
institutions
  └── schools
       └── grades
            └── groups
                 └── students ──── guardians
                                      │
                                   (email de notificación)

users (docentes)
  └── asignados a groups

pae_deliveries          → student, user (docente), fecha, método de registro
attendance_records      → student, group, fecha, clase, estado
attendance_tokens       → token único por inasistencia, expira a medianoche
discipline_records      → student, user, artículos, observaciones, firma (base64)
early_departures        → student, user, fecha, hora
notifications_log       → registro de cada correo enviado (estado, timestamp)
import_jobs             → estado de cargas masivas (pendiente/procesando/completado/error)
```

### Tokens de justificación de inasistencia

- JWT firmado con expiración a medianoche del día actual.
- Adicionalmente almacenado en BD con estado `used/unused`.
- Un token válido criptográficamente pero marcado como `used` se rechaza. Esto impide que el mismo enlace se use más de una vez.

---

## 5. Carga masiva de datos (Excel)

El onboarding inicial de estudiantes, acudientes y configuración institucional se realiza mediante importación de archivos `.xlsx`.

**Flujo:**

1. `POST /admin/import/students` recibe el archivo.
2. El endpoint persiste el archivo en storage y encola un job Celery.
3. El job procesa las filas en background: valida, crea o actualiza registros.
4. Al finalizar, persiste un reporte en `import_jobs` con filas OK y filas con error + motivo.
5. El cliente puede consultar `GET /admin/import/{job_id}` para ver el estado.

**Comportamiento ante errores**: carga parcial. Las filas válidas se procesan; las inválidas se reportan. No se rechaza el lote completo por errores individuales.

---

## 6. Principios SOLID aplicados

### S — Single Responsibility

Cada capa tiene exactamente una razón para cambiar:
- El Router cambia si cambia el contrato HTTP.
- El Service cambia si cambia la lógica de negocio.
- El Repository cambia si cambia la forma de persistir datos.

### O — Open/Closed

Los Services se extienden sin modificarse. Nuevos comportamientos se agregan implementando el Protocol correspondiente (ver sección de patrones), no modificando código existente.

### I — Interface Segregation

Los schemas Pydantic separan explícitamente lo que entra (`StudentCreate`) de lo que sale (`StudentResponse`). Ningún cliente recibe más datos de los que necesita, y ningún endpoint acepta más campos de los que debe.

### D — Dependency Inversion

Las dependencias se inyectan vía `Depends()` de FastAPI. Los Services reciben sus Repositories y Adapters como parámetros, no los instancian internamente. Esto permite reemplazar implementaciones en tests sin tocar el código de producción.

```python
# Correcto
def get_pae_service(
    repo: PAERepository = Depends(get_pae_repository),
    email: EmailAdapter = Depends(get_email_adapter),
) -> PAEService:
    return PAEService(repo, email)

# Incorrecto — el service conoce y controla sus dependencias
class PAEService:
    def __init__(self):
        self.repo = PAERepository()  # acoplamiento duro
```

> **Nota sobre Liskov (L):** El proyecto no usa jerarquías de herencia profundas, por lo que LSP no aplica como restricción frecuente. Donde sí aplica es en los Adapters: cualquier implementación concreta (Resend, SES) debe ser intercambiable sin que el código que la usa lo note. Eso se garantiza cumpliendo el Protocol definido.

---

## 7. Patrones de diseño

### Strategy — Registro PAE

El módulo PAE admite dos mecanismos de identificación del estudiante: reconocimiento facial (fase 2) y búsqueda por número de documento (MVP). Ambos son estrategias intercambiables para el mismo resultado.

```python
from typing import Protocol
from app.models.student import Student

class PAEIdentificationStrategy(Protocol):
    def identify(self, input_data: dict) -> Student:
        ...

class DocumentSearchStrategy:
    def identify(self, input_data: dict) -> Student:
        document = input_data["document_number"]
        # busca en BD y retorna Student
        ...

class FacialRecognitionStrategy:
    def identify(self, input_data: dict) -> Student:
        # llama al servicio de reconocimiento facial
        # retorna Student — misma interfaz, distinta implementación
        ...

class PAEService:
    def __init__(self, strategy: PAEIdentificationStrategy):
        self.strategy = strategy

    def register_delivery(self, input_data: dict, docente_id: int):
        student = self.strategy.identify(input_data)
        # resto del flujo es idéntico independientemente de la estrategia
        ...
```

**Beneficio directo**: cuando se agregue reconocimiento facial en fase 2, no se modifica `PAEService`. Se implementa `FacialRecognitionStrategy` y se inyecta.

---

### Adapter — Servicios externos

Email y storage son externos y pueden cambiar de proveedor. Se abstraen detrás de un Protocol para que el resto del código sea independiente de la implementación concreta.

#### Email Adapter

```python
from typing import Protocol

class EmailAdapter(Protocol):
    def send(self, to: str, subject: str, html: str) -> None:
        ...

class ResendEmailAdapter:
    def send(self, to: str, subject: str, html: str) -> None:
        # implementación con Resend SDK
        ...

class SESEmailAdapter:
    def send(self, to: str, subject: str, html: str) -> None:
        # implementación con boto3 SES
        ...
```

#### Storage Adapter

```python
from typing import Protocol

class StorageAdapter(Protocol):
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        ...

    def get_url(self, key: str) -> str:
        ...

class S3StorageAdapter:
    def __init__(self, endpoint_url: str, bucket: str):
        # endpoint_url apunta a MinIO en local, a S3 en prod
        ...

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        ...

    def get_url(self, key: str) -> str:
        ...
```

La implementación activa se selecciona en `core/config.py` según variables de entorno. El resto del código solo conoce el Protocol.

---

## 8. Decisiones explícitamente descartadas

| Decisión | Motivo del descarte |
|---|---|
| Microservicios | El volumen de tráfico y la complejidad del dominio no lo justifican en el MVP. Agrega overhead operativo sin beneficio real. |
| DDD (Domain-Driven Design) | El dominio no tiene reglas de negocio suficientemente complejas para justificar Aggregates, Domain Events y la ceremonia asociada. |
| Clean Architecture | Las capas de indirección (puertos, adaptadores, casos de uso) generan boilerplate puro en Python sin agregar valor sobre la arquitectura por capas elegida. |
| Reconocimiento facial en MVP | Requiere foto de referencia por estudiante, condiciones de iluminación controladas y calibración de umbrales. El flujo por documento ya resuelve el problema. Se evalúa en fase 2. |
| Factory / Builder | No existen objetos con construcción suficientemente compleja que lo justifiquen. |
| Observer para notificaciones | Celery ya actúa como mecanismo de eventos. Agregar Observer sería duplicar responsabilidades. |
| Template Method para correos | La variación entre notificaciones es de contenido, no de flujo. Se resuelve con parámetros, no con herencia. |

---

*Documento de arquitectura — BIGA APP | Versión 1.0 | Mayo 2026*
