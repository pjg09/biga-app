# BIGA — Landing Page

## Hero

**BIGA**
Tecnología al servicio de la comunidad educativa

> Corresponsabilidad, protección y bienestar para niños, niñas y adolescentes.

[Conoce más] [Solicita una demo]

---

## Misión

Impulsar en la comunidad educativa una cultura de corresponsabilidad orientada a la protección integral de niños, niñas y adolescentes, mediante el uso ético, consciente y regulado de la tecnología.

A través del desarrollo e implementación de soluciones digitales innovadoras, BIGA fortalece la comunicación efectiva entre familia, escuela e institución, facilitando el seguimiento oportuno de procesos académicos, convivenciales y de garantía de derechos como la asistencia y la alimentación.

Integrando analítica de datos e inteligencia artificial, se promueve la prevención de riesgos asociados al entorno digital y se potencian condiciones esenciales del aprendizaje como la atención, la emoción y la memoria, contribuyendo al bienestar y desarrollo pleno de los estudiantes.

---

## Visión

Consolidarse como un modelo referente en la transformación educativa y social, que articula tecnología, corresponsabilidad y enfoque de derechos para construir entornos protectores, seguros y conscientes.

A mediano y largo plazo, BIGA integrará de manera progresiva los procesos académicos, convivenciales, administrativos y jurídicos, apoyado en herramientas digitales inteligentes que permitan decisiones oportunas y pertinentes.

Se proyecta como una iniciativa sostenible que, además de fortalecer la calidad educativa, promueve el uso responsable de la tecnología, la innovación con sentido social y el desarrollo integral de las comunidades educativas.

---

## ¿Qué hace BIGA?

### Comunicación familia-escuela
Canales directos y trazables entre padres, docentes e institución para que nada se pierda.

### Seguimiento académico y convivencial
Registro en tiempo real de asistencia, alimentación PAE y procesos de convivencia escolar.

### Analítica e inteligencia artificial
Detección temprana de riesgos y patrones que afectan el aprendizaje y el bienestar estudiantil.

### Protección de derechos
Herramientas alineadas con el enfoque de garantía de derechos de niños, niñas y adolescentes.

---

## ¿Para quién es BIGA?

- **Instituciones educativas** que necesitan digitalizar y centralizar sus procesos.
- **Docentes y coordinadores** que requieren trazabilidad en tiempo real.
- **Familias** que quieren estar informadas y participar activamente.
- **Secretarías de educación** que buscan datos confiables para tomar decisiones.

---

## Identidad

- **Color principal**: Morado — tecnología con propósito social.
- **Nombre**: BIGA
- **Enfoque**: Ético, consciente y orientado al desarrollo integral.

---

## Llamado a la acción

¿Listo para transformar tu comunidad educativa?

[Solicita una demo gratuita]

### Implementación (módulo `leads`)

El formulario **no es decorativo**: `CallToAction.jsx` hace `POST /leads` (público, sin JWT) y solo
muestra "¡Gracias!" cuando el backend responde 201. Hasta 2026-08-13 era un placeholder que descartaba
el correo en memoria mostrando un éxito falso.

- El lead se guarda **siempre** en `demo_leads`; el aviso interno por correo a `LEADS_NOTIFY_EMAIL` es
  un efecto secundario asíncrono (job Celery). Si el correo falla, el lead no se pierde.
- Rate limit por IP en Redis (5/hora). Si Redis cae, **deja pasar** la petición: perder un lead es peor
  que aceptar un envío de más.
- Un mismo correo dentro de 24 h se guarda pero se marca `SUPPRESSED` y no genera segundo aviso.
- Se consultan en la consola de admin: **Comercial → Solicitudes** (`GET /admin/leads`).

Ver `docs/database-schema.md` para la tabla y `CLAUDE.md` para la decisión de dejarla fuera del tenant.

---

*BIGA — Construyendo entornos protectores con tecnología.*
