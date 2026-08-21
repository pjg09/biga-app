# General

- [ ] Validar si es necesario segmentar algunos archivos muy largos del front en componentes
- [ ] Dejar el sistema de correos funcional en producción
- [ ] Aplicar la o las nuevas variables de entorno a producción junto con la migración
- [ ] Revisar la suite de tests, unitarios, compuestos, por capa, con infraestructura y revisar aqui tambien la parte del workflow de github para que se haga lo que se debe hacer en el push a main
- [ ] Revisar que buenas practicas se pueden aplicar en el backend y en el frontend
- [ ] Mirar que se puede optimizar a nivel de código para que sea más eficiente
- [ ] Mirar que se puede optimizar a nivel de infraestructura, pool de conexiones y accesos o base de datos o creacion de conexiones, lo que sea que aplique dentro del proyecto
- [ ] Script para borrar huerfanos del bucket
- [ ] Mirar si se puede optimizar algún endpoint
- [ ] Modo oscuro, claro o modo del sistema en la barra de navegación lateral
- [ ] Sección de ayuda con form para soporte/feedback y FAQ

# TEMPORAL — revertir antes de producción real

- [ ] **Operación de sábado y domingo habilitada para el QA de los product owners.**
      Qué se tocó, y qué decidir al salir a producción:
      - `class_periods.day_of_week` acepta **1..7** (`CHECK`, migración `c5b9e2f47a13`). Se dejó
        así porque ya existían bloques en sábado creados por API; estrecharlo a 1..5 exigiría
        borrarlos. **Decisión pendiente**: la mayoría de colegios públicos opera Lun–Vie.
      - La rejilla de Horarios tiene un check **«Fin de semana»** (`showWeekend` en
        `HorarioGrid`) que fuerza las columnas Sáb/Dom aunque estén vacías, para poder crear
        bloques ahí. Si producción es Lun–Vie, quitar ese check.
      - El modal «Crear jornada» ofrece los 7 días. Si producción es Lun–Vie, dejarlo en 1..5.
      - **El backend no tuvo que cambiarse**: no hay ninguna restricción por día de la semana
        (`attendance_service` usa `isoweekday()` 1..7 y el beat del PAE corre todos los días).
        Si algún día hay que bloquear el fin de semana, hoy **no existe** ese punto de control:
        habría que crearlo.
- [ ] Revertir `ATTENDANCE_GRACE_MINUTES` a 50 (está en 2 para pruebas).
- [ ] `EMAIL_PROVIDER=mailtrap` es solo para el entorno de QA. Producción va con `resend` y
      dominio verificado — si se despliega con mailtrap, **ningún acudiente recibe nada**.

# Preguntas para los stakeholders

- [ ] Cuántos documentos se deberían poder adjuntar en una justificación por inasistencia?
- [ ] En las salidas tempranas de hoy solo se muestran las salidas tempranas registradas hoy por ese maestro/usuario, así está bien o que debería mostrar?
