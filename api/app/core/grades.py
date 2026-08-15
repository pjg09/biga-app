"""Catálogo fijo de grados.

Los grados **no se crean desde la aplicación**: los colegios públicos de
Medellín tienen siempre los mismos 11 niveles de básica y media, así que son un
catálogo, no un dato que el admin dé de alta. La consola no expone ningún alta
de grados y `POST /admin/grades` no existe.

Cada institución tiene sus propias 11 filas porque `grades` lleva
`institution_id` (ver `docs/database-schema.md`). Las siembra la migración
`a7c3e9f2b581` para las instituciones ya existentes, y `scripts/seed_base.py`
para las nuevas.

Si alguna vez hay que añadir preescolar o transición, se cambia esta lista y se
escribe una migración nueva que la aplique — no se reabre el alta manual.
"""

STANDARD_GRADES: list[tuple[int, str]] = [
    (1, "Primero"),
    (2, "Segundo"),
    (3, "Tercero"),
    (4, "Cuarto"),
    (5, "Quinto"),
    (6, "Sexto"),
    (7, "Séptimo"),
    (8, "Octavo"),
    (9, "Noveno"),
    (10, "Décimo"),
    (11, "Once"),
]
