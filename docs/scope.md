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

| Perfil | Descripción |
|---|---|
| **Docente** | Usuario operativo principal. Registra asistencia, gestiona entregas del PAE y crea registros en el agendatorio desde su dispositivo móvil. |
| **Acudiente** | Padre de familia o responsable del estudiante. Recibe notificaciones por correo electrónico e interactúa con la plataforma únicamente a través de enlaces únicos para justificar inasistencias. |
| **Estudiante** | Referente pasivo dentro del sistema. Es identificado en los módulos de PAE y asistencia, y firma registros en el agendatorio. |

> Los perfiles de administración institucional (rector, coordinador, secretaria) quedan fuera del alcance del MVP y serán evaluados en fases posteriores.

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

## 4. Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Base de datos** | PostgreSQL |
| **Backend** | Python (sin framework web adicional) |
| **API** | FastAPI |
| **Frontend** | Preact |
| **Deploy** | Por definir |

---

*Documento de alcance — BIGA APP | Versión 1.0 | Abril 2026*
