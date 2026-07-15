# Documentación de BIGA

Índice de la documentación del proyecto. Para las reglas de trabajo (con IA o
manual) ver `CLAUDE.md` en la raíz.

## Empezar

| Doc | Para qué |
|---|---|
| [runbook.md](runbook.md) | Cómo levantar el stack, credenciales de prueba y troubleshooting. |
| [scope.md](scope.md) | Alcance y requerimientos del MVP (la fuente de verdad de qué se construye). |

## Arquitectura y modelo

| Doc | Para qué |
|---|---|
| [architecture.md](architecture.md) | Decisiones de arquitectura del backend: capas, adapters, jobs, storage. |
| [frontend.md](frontend.md) | Arquitectura del cliente React: routing, auth, servicios, dashboards, CSS. |
| [database-schema.md](database-schema.md) | Esquema de la base de datos (tablas, enums, índices, extensiones). |
| [implementation-notes.md](implementation-notes.md) | Restricciones no obvias por capa (multi-tenant, patrones). |

## Referencia funcional por módulo

| Doc | Módulo |
|---|---|
| [attendance.md](attendance.md) | Asistencia clase a clase, tardanzas, justificación por link, salidas tempranas. |
| [pae.md](pae.md) | Programa de Alimentación Escolar: inscripción, entrega, doble hash, reporte. |
| [agendatorio.md](agendatorio.md) | Convivencia: registro con firma, notificación, historial (notas + ocultar). |

## Otros

| Doc | Para qué |
|---|---|
| [databaseDev.md](databaseDev.md) | Credenciales de los usuarios demo (seed de desarrollo). |
| [landing-page.md](landing-page.md) | Especificación de contenido de la landing pública. |
