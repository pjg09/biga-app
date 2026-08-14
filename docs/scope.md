# BIGA APP — Documento de Alcance del Proyecto

---

## 1. Descripción General del Proyecto

BIGA es una aplicación web mobile-first orientada al entorno educativo colombiano, diseñada para resolver dos problemas concretos que hoy afectan a las instituciones educativas públicas del país:

**Control del PAE (Programa de Alimentación Escolar)**
El PAE es un programa público de alimentación estudiantil que en la actualidad opera sin trazabilidad confiable. No existe un mecanismo que garantice qué estudiante reclamó su alimento, cuándo lo hizo, ni que impida dobles registros o entregas a personas no autorizadas. BIGA plantea digitalizar y formalizar este proceso, dándole integridad referencial a cada entrega.

**Comunicación colegio–acudiente**
Existe una brecha importante entre lo que ocurre dentro de la institución educativa y el conocimiento que tienen los padres o acudientes sobre la situación de sus hijos. Hoy esa comunicación depende de canales informales como grupos de WhatsApp o llamadas telefónicas que no dejan trazabilidad. BIGA propone un canal de comunicación formal y automatizado que mantenga informados a los acudientes en tiempo real sobre eventos relevantes de sus estudiantes.

### MVP — Alcance inicial

Para la primera versión de la aplicación se priorizan las siguientes notificaciones automáticas hacia el acudiente:

- Inasistencia del estudiante a la primera hora de clase
- Registro de una sanción en el agendatorio (libro de convivencia)
- Estudiante registrado en el PAE que no reclamó su alimento en el día

---

## 2. Perfiles de Usuario

| Perfil (rol) | Descripción |
|---|---|
| **Docente** (`TEACHER`) | Usuario operativo de aula. Registra asistencia, salidas tempranas y registros de convivencia desde su dispositivo móvil. |
| **Operador PAE** (`PAE_OPERATOR`) | Es un docente con funciones extra del PAE: además de todo lo de aula, gestiona inscripciones y entregas del PAE. Comparte los endpoints de aula vía `require_staff`. |
| **Administrador** (`ADMIN`) | Consulta estadísticas institucionales (`GET /admin/stats`) y opera la consola de gestión: alta de estudiantes (con matrícula y acudientes), personal, académico (grados/salones), horarios y asignación docente-grupo. Único rol que matricula estudiantes al PAE y que lee las solicitudes de demo de la landing. |
| **Acudiente** | Padre de familia o responsable del estudiante. Recibe notificaciones por correo e interactúa solo a través de enlaces únicos para justificar inasistencias. |
| **Estudiante** | Referente pasivo dentro del sistema. Es identificado en los módulos de PAE y asistencia, y firma registros en el agendatorio. |

> El perfil **Administrador** se incorporó con un dashboard de estadísticas. Perfiles institucionales más finos (rector, coordinador, secretaría con permisos diferenciados) quedan para fases posteriores.

---

## 3. Módulos y Funcionalidades

### 3.1 Módulo PAE — Control de Entrega del Programa de Alimentación Escolar

**Objetivo:** Garantizar que cada entrega del PAE quede registrada digitalmente, vinculada al estudiante correcto, con trazabilidad completa y sin posibilidad de doble registro en el mismo día.

**Flujo principal — Registro por reconocimiento facial:**

1. El docente con permisos de PAE inicia sesión desde su celular.
2. Accede al portal del PAE, donde se carga automáticamente el listado de estudiantes beneficiarios del PAE para ese día.
3. El docente activa la cámara del dispositivo y apunta al rostro del estudiante.
4. El sistema realiza el reconocimiento facial y busca coincidencia dentro del listado del día:
   - Si hay coincidencia: muestra el perfil del estudiante y habilita el botón de registro de entrega.
   - Si no hay coincidencia o el estudiante no está en el listado: informa que el estudiante no está habilitado para recibir PAE ese día.
5. Al confirmar la entrega, el sistema registra qué estudiante recibió el alimento y qué docente realizó la entrega. El estudiante queda bloqueado para ese día (no puede recibir una segunda entrega).

**Flujo alternativo — Registro por número de documento:**

1. El docente ingresa el número de documento del estudiante en un campo de búsqueda.
2. El sistema localiza al estudiante y muestra un perfil con foto y nombre para corroborar identidad.
3. El docente confirma la entrega desde ese perfil. El sistema registra qué estudiante recibió el alimento y qué docente realizó la entrega.

**Job automático al finalizar el descanso:**

- Se ejecuta un proceso programado al cierre del horario de entrega del PAE.
- El job identifica a los estudiantes del listado que no recibieron su alimento ese día.
- Se envía un correo electrónico automático al acudiente de cada uno de estos estudiantes, notificando que su hijo/a no reclamó el PAE en la fecha.

---

### 3.2 Módulo de Asistencia — Control y Seguimiento de Asistencia por Clase

**Objetivo:** Digitalizar el registro de asistencia clase por clase, mantener un historial por estudiante y activar comunicación automática con acudientes ante inasistencias en la primera hora.

**Flujo de registro:**

1. Al inicio de cada clase, el docente inicia sesión y accede a la vista de asistencia correspondiente a esa clase.
2. El sistema carga el listado de estudiantes del grupo.
3. El docente recorre el listado marcando la asistencia de cada estudiante (presente / ausente).
4. El registro queda almacenado con fecha, hora y clase, permitiendo construir un historial de asistencia por estudiante.

**Job de notificación por inasistencia en primera hora:**

- Si un estudiante es marcado como ausente en la primera clase del día, se desencadena un proceso automático.
- Se envía un correo electrónico al acudiente notificando la inasistencia y que se asume que el estudiante no asistió al colegio ese día.
- El correo incluye un **enlace único, de uso individual y válido solo para ese día**, que lleva al acudiente a un formulario donde debe:
  - Indicar la razón de la inasistencia de su hijo.
  - Enviar el formulario para que el motivo quede registrado y vinculado a esa inasistencia específica.

---

### 3.3 Módulo Agendatorio — Registro de Convivencia Escolar

**Objetivo:** Digitalizar el libro de convivencia escolar, reemplazando el registro en papel y habilitando notificaciones automáticas al acudiente ante sanciones disciplinarias.

**Flujo de registro:**

1. El docente accede a la sección de agendatorio desde su portal.
2. Realiza una búsqueda por grado, salón o nombre del estudiante para ubicar al implicado.
3. El sistema carga el manual de convivencia de la institución. El docente selecciona el o los artículos que el estudiante incumplió.
4. El docente completa los siguientes campos:
   - **Artículos del manual de convivencia incumplidos** (selección desde listado)
   - **Observaciones** (campo de texto libre para descripción del hecho)
   - **Firma del estudiante** (captura mediante trazado con el dedo sobre la pantalla del dispositivo móvil)
5. Al guardar el registro, se envía una notificación al acudiente informando que su hijo/a tiene un nuevo registro en el agendatorio.

### 3.4 Módulo de Salidas Tempranas — Reporte de Retiro Anticipado

**Objetivo:** Registrar y notificar al acudiente cuando un estudiante abandona la institución antes del horario regular de salida.

**Flujo de registro:**

1. El docente accede a la vista de salidas tempranas desde su portal.
2. Busca al estudiante que se va a retirar anticipadamente.
3. Registra la salida temprana del estudiante.
4. El sistema ejecuta un job que envía una notificación por correo electrónico al acudiente informando que su hijo/a se retiró de la institución antes de la hora habitual de salida.

---

### 3.5 Módulo de Gestión Administrativa — Consola del Administrador

**Objetivo:** Darle al Administrador las herramientas para construir y mantener la
estructura de la institución (personal, grados, salones, horarios) y dar de alta
estudiantes con su matrícula y acudientes, sin depender de una carga manual en la base de
datos.

**Flujo de alta de estudiante:**

1. El Administrador abre "Estudiantes" en su consola y registra documento, nombres, fecha
   de nacimiento y opcionalmente una foto.
2. Opcionalmente lo matricula a un grado y salón existentes.
3. Registra al menos un acudiente, marcando exactamente uno como principal — es quien
   recibe las notificaciones automáticas de PAE, asistencia y convivencia de ese estudiante.
4. El sistema guarda estudiante, matrícula y acudientes de forma atómica: si algo falla, no
   queda un estudiante a medias.

**Gestión de estructura institucional:**

- Alta de personal (docentes, operadores PAE, administradores) con rol y credenciales.
- Alta de grados y salones, y matrícula de estudiantes ya existentes a un salón.
- Definición de horarios de clase (bloques por salón, día y hora) y asignación de
  docentes a los salones que les corresponden — de esto depende qué estudiantes ve cada
  docente en Asistencia y en "Mis estudiantes".
- Es el único rol que matricula estudiantes al PAE (decisión administrativa, distinta de
  *operar* el programa día a día, que hace el Operador PAE).
- Consulta el panel de estadísticas institucionales y la bandeja de solicitudes de demo
  recibidas desde la landing pública.

> Referencia funcional completa (endpoints, reglas de validación, roles exactos) en
> `docs/admin.md` y `docs/students.md`.

---

## 4. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Base de datos** | PostgreSQL |
| **Backend** | Python (sin framework web adicional) |
| **API** | FastAPI |
| **Frontend** | React |
| **Deploy** | Por definir |

---

*Documento de alcance — BIGA APP | Versión 1.0 | Abril 2026*
