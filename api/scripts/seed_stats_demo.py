"""Historia sintética para poder ver (y verificar) el módulo de Estadísticas.

La BD de desarrollo tiene 6 estudiantes y dos semanas de datos: con eso ninguna
estadística significa nada — una tasa sobre 16 registros es ruido, y los errores
de agregación (un JOIN que duplica filas, un divisor equivocado) no se notan
porque cualquier número parece plausible. Este script genera ~12 semanas de
operación de un colegio de tamaño creíble para que las cifras se puedan contrastar.

    docker compose exec -T api python -m scripts.seed_stats_demo
    docker compose exec -T api python -m scripts.seed_stats_demo --limpiar

Es Python y no SQL porque las entregas del PAE llevan la cadena de doble hash,
que depende de `PAE_SIGNING_SECRET` (mismo motivo que `seed_pae.py`).

**Solo toca lo que él mismo crea**: estudiantes con documento `99…` y sus filas
dependientes, más los salones y bloques marcados abajo. `--limpiar` los borra en
orden inverso de dependencias. No modifica los datos demo previos.

Qué genera, y por qué así:

- **Perfiles de asistencia** (regular / intermitente / crónico) en vez de un
  porcentaje uniforme: sin dispersión entre estudiantes, la vista de riesgo sale
  vacía y no se puede comprobar que ordena bien.
- **Solo 4 de los 6 bloques diarios** llevan lista tomada: la cobertura de
  registro tiene que salir por debajo del 100% para que se vea que la métrica
  funciona y que la alerta correspondiente dispara.
- **Efecto día de semana y hora**: lunes y viernes peores, últimas horas peores.
  Son los patrones que esas dos gráficas deben revelar; si el generador no los
  mete, no hay forma de saber si las consultas los detectarían.
"""
import asyncio
import random
import sys
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, insert, select, text

from app.core.database import AsyncSessionLocal
from app.core.security import compute_delivery_hash, compute_enrollment_hash, hash_password
from app.models.attendance import AttendanceJustification, AttendanceRecord, AttendanceToken
from app.models.agendatorio import DisciplineRecord, DisciplineRecordArticle
from app.models.class_period import ClassPeriod
from app.models.departure import EarlyDeparture
from app.models.enums import (
    AttendanceStatus,
    UserRole,
    GuardianRelationship,
    NotificationStatus,
    NotificationType,
    PAEIdentificationMethod,
)
from app.models.grade import Grade
from app.models.group import Group
from app.models.guardian import Guardian
from app.models.notification import NotificationLog
from app.models.pae import PAEDelivery, PAEEnrollment
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user import User
from app.models.user_group import UserGroup

INSTITUTION_ID = UUID("a0000000-0000-0000-0000-000000000001")
PAE_USER_ID = UUID("b0000000-0000-0000-0000-000000000002")
DOC_PREFIJO = "99"          # marca de "estudiante generado por este script"
DOC_PREFIJO_DOCENTE = "98"  # ídem para los docentes que crea si faltan
SEMANAS = 12
BLOQUES_CON_LISTA = 4       # de 6; deja la cobertura por debajo del 100%

SALONES = [("Once", "B"), ("Décimo", "A"), ("Décimo", "B")]
ESTUDIANTES_POR_SALON = 22

NOMBRES = ["Mariana", "Santiago", "Valentina", "Mateo", "Isabella", "Samuel", "Sofía",
           "Emiliano", "Camila", "Tomás", "Salomé", "Juan José", "Antonella", "Martín",
           "Luciana", "Nicolás", "Gabriela", "Andrés", "Manuela", "Sebastián", "Daniela",
           "Alejandro", "Paulina", "Felipe", "Renata", "Simón"]
APELLIDOS = ["Gómez", "Restrepo", "Ospina", "Cardona", "Vélez", "Zapata", "Arango",
             "Muñoz", "Quintero", "Betancur", "Rincón", "Agudelo", "Mesa", "Duque",
             "Hoyos", "Álvarez", "Ramírez", "Castaño"]

MOTIVOS_SALIDA = ["Cita médica", "Calamidad familiar", "Cita odontológica",
                  "Diligencia con acudiente", "Malestar general"]
OBSERVACIONES = [
    "Interrumpe la clase de forma reiterada pese a los llamados de atención.",
    "Uso del celular durante la evaluación.",
    "Agresión verbal a un compañero en el descanso.",
    "Incumplimiento del manual de convivencia en el uso del uniforme.",
    "Sale del aula sin autorización del docente.",
]

# Semilla fija: dos corridas dan el mismo colegio, así que las cifras se pueden
# comparar entre ejecuciones al depurar una consulta.
random.seed(20260815)


def dias_habiles(semanas: int) -> list[date]:
    hoy = date.today()
    dias = []
    d = hoy - timedelta(days=semanas * 7)
    while d <= hoy:
        if d.weekday() < 5:
            dias.append(d)
        d += timedelta(days=1)
    return dias


async def limpiar(db):
    """Borra en orden inverso de dependencias. Los estudiantes generados se
    identifican por el prefijo de documento; los salones, por su nombre."""
    ids = (await db.execute(
        select(Student.id).where(
            Student.institution_id == INSTITUTION_ID,
            Student.document_number.like(f"{DOC_PREFIJO}%"),
        )
    )).scalars().all()
    if ids:
        recs = (await db.execute(
            select(AttendanceRecord.id).where(AttendanceRecord.student_id.in_(ids))
        )).scalars().all()
        if recs:
            await db.execute(delete(AttendanceJustification).where(
                AttendanceJustification.attendance_record_id.in_(recs)))
            await db.execute(delete(AttendanceToken).where(
                AttendanceToken.attendance_record_id.in_(recs)))
        drs = (await db.execute(
            select(DisciplineRecord.id).where(DisciplineRecord.student_id.in_(ids))
        )).scalars().all()
        if drs:
            await db.execute(delete(DisciplineRecordArticle).where(
                DisciplineRecordArticle.discipline_record_id.in_(drs)))
        for modelo in (NotificationLog, AttendanceRecord, DisciplineRecord, EarlyDeparture,
                       PAEDelivery, PAEEnrollment, StudentGroup, Guardian):
            await db.execute(delete(modelo).where(modelo.student_id.in_(ids)))
        await db.execute(delete(Student).where(Student.id.in_(ids)))

    grupos = (await db.execute(
        select(Group.id).join(Grade, Grade.id == Group.grade_id).where(
            Group.institution_id == INSTITUTION_ID,
            Group.name.in_([s for _, s in SALONES]),
            Grade.name.in_([g for g, _ in SALONES]),
        )
    )).scalars().all()
    # 11A del seed original también es ("Once", "A"): se excluye explícitamente.
    grupos = [g for g in grupos if g != UUID("e0000000-0000-0000-0000-000000000001")]
    if grupos:
        await db.execute(delete(ClassPeriod).where(ClassPeriod.group_id.in_(grupos)))
        await db.execute(delete(UserGroup).where(UserGroup.group_id.in_(grupos)))
        await db.execute(delete(StudentGroup).where(StudentGroup.group_id.in_(grupos)))
        await db.execute(delete(Group).where(Group.id.in_(grupos)))

    # Los docentes que el seed creó por falta de planta. Se borran al final,
    # cuando ya no queda ningún bloque ni asistencia apuntando a ellos.
    docs = (await db.execute(
        select(User.id).where(
            User.institution_id == INSTITUTION_ID,
            User.document_number.like(f"{DOC_PREFIJO_DOCENTE}%"),
        )
    )).scalars().all()
    if docs:
        await db.execute(delete(UserGroup).where(UserGroup.user_id.in_(docs)))
        await db.execute(delete(User).where(User.id.in_(docs)))
    await db.commit()
    print(f"Limpiado: {len(ids)} estudiantes, {len(grupos)} salones, "
          f"{len(docs)} docentes y sus dependencias.")


async def seed(db):
    anio = date.today().year
    docentes = (await db.execute(
        select(User).where(User.institution_id == INSTITUTION_ID, User.is_active == True)
    )).scalars().all()
    docentes = [u for u in docentes if u.role.value != "ADMIN"] or docentes
    articulos = (await db.execute(
        text("SELECT id FROM convivencia_articles WHERE institution_id = :i AND is_active"),
        {"i": INSTITUTION_ID},
    )).scalars().all()

    # --- Salones + horario ---
    grupos: list[Group] = []
    for grado_nombre, salon in SALONES:
        grade_id = (await db.execute(
            select(Grade.id).where(Grade.institution_id == INSTITUTION_ID,
                                   Grade.name == grado_nombre).limit(1)
        )).scalar_one_or_none()
        if not grade_id:
            print(f"  · sin grado «{grado_nombre}», se omite")
            continue
        existente = (await db.execute(
            select(Group).where(Group.institution_id == INSTITUTION_ID,
                                Group.grade_id == grade_id, Group.name == salon,
                                Group.academic_year == anio)
        )).scalar_one_or_none()
        g = existente or Group(id=uuid4(), institution_id=INSTITUTION_ID, grade_id=grade_id,
                               name=salon, academic_year=anio)
        if not existente:
            db.add(g)
        grupos.append(g)
    await db.flush()

    horas = [(time(7, 0), time(7, 50)), (time(7, 50), time(8, 40)), (time(8, 40), time(9, 30)),
             (time(10, 0), time(10, 50)), (time(10, 50), time(11, 40)), (time(11, 40), time(12, 30))]

    # Ocupación real de cada docente, precargada con TODO lo que ya hay en la BD
    # (incluido el horario de 11A del seed original). Sin esto, la versión previa
    # repartía docentes por índice y dejó al mismo profesor en cuatro salones a
    # las 07:00 — que es exactamente lo que la constraint `b7e4f1c8a209` prohíbe
    # ahora, así que el seed fallaría al insertar.
    ocupacion: dict[tuple[UUID, int], list[tuple[time, time]]] = {}
    for cp in (await db.execute(select(ClassPeriod))).scalars().all():
        ocupacion.setdefault((cp.user_id, cp.day_of_week), []).append((cp.start_time, cp.end_time))

    def libre(user_id: UUID, dia: int, ini: time, fin: time) -> bool:
        return all(not (ini < f and i < fin) for i, f in ocupacion.get((user_id, dia), []))

    pool = list(docentes)
    creados_docentes = 0

    async def docente_para(dia: int, ini: time, fin: time) -> User:
        """Primer docente libre en esa franja; si no hay ninguno, crea uno.

        Un colegio con 4 salones necesita al menos 4 docentes por franja. La BD
        demo tenía 4 activos en total, así que era imposible cubrir el horario
        sin duplicar a alguien: el seed tiene que poder ampliar la planta.
        """
        nonlocal creados_docentes
        for u in pool:
            if libre(u.id, dia, ini, fin):
                ocupacion.setdefault((u.id, dia), []).append((ini, fin))
                return u
        creados_docentes += 1
        n = creados_docentes
        nuevo_doc = User(
            id=uuid4(), institution_id=INSTITUTION_ID,
            document_number=f"{DOC_PREFIJO_DOCENTE}{n:06d}",
            first_name=random.choice(NOMBRES), last_name=random.choice(APELLIDOS),
            email=f"docente.demo{n}@iedemo.edu.co",
            hashed_password=hash_password("password123"),
            role=UserRole.TEACHER, is_active=True,
        )
        db.add(nuevo_doc)
        await db.flush()
        pool.append(nuevo_doc)
        ocupacion.setdefault((nuevo_doc.id, dia), []).append((ini, fin))
        return nuevo_doc

    bloques: dict[UUID, list[ClassPeriod]] = {}
    for g in grupos:
        ya = (await db.execute(
            select(ClassPeriod).where(ClassPeriod.group_id == g.id)
        )).scalars().all()
        if ya:
            bloques[g.id] = sorted(ya, key=lambda c: (c.day_of_week, c.period_order))
            continue
        creados, del_salon = [], set()
        for dow in range(1, 6):
            for i, (ini, fin) in enumerate(horas, start=1):
                doc = await docente_para(dow, ini, fin)
                del_salon.add(doc.id)
                cp = ClassPeriod(
                    id=uuid4(), institution_id=INSTITUTION_ID, group_id=g.id,
                    name=f"{i}ª hora", period_order=i, start_time=ini, end_time=fin,
                    day_of_week=dow, user_id=doc.id,
                )
                db.add(cp)
                creados.append(cp)
        bloques[g.id] = creados
        # `user_groups` para los docentes que de verdad dictan en ese salón: es
        # lo que decide qué estudiantes ve cada uno en «Mis estudiantes».
        for uid in del_salon:
            db.add(UserGroup(id=uuid4(), user_id=uid, group_id=g.id, academic_year=anio))
    await db.flush()
    if creados_docentes:
        print(f"  · {creados_docentes} docentes creados (no había suficientes libres)")

    # --- Estudiantes ---
    doc = 1
    estudiantes: list[tuple[Student, Group, str]] = []
    # `notifications_log.guardian_id` es NOT NULL con FK: hay que conservar el
    # acudiente de cada estudiante para poder registrar los avisos.
    guardianes: dict[UUID, UUID] = {}
    for g in grupos:
        for _ in range(ESTUDIANTES_POR_SALON):
            # 5% ausentismo crónico, 15% intermitente: la dispersión es lo que
            # hace verificable la vista de riesgo.
            r = random.random()
            perfil = "cronico" if r < 0.05 else "intermitente" if r < 0.20 else "regular"
            s = Student(
                id=uuid4(), institution_id=INSTITUTION_ID,
                document_number=f"{DOC_PREFIJO}{doc:08d}",
                first_name=random.choice(NOMBRES), last_name=random.choice(APELLIDOS),
                birth_date=date(anio - random.randint(14, 17), random.randint(1, 12), 15),
                is_active=True,
            )
            doc += 1
            db.add(s)
            estudiantes.append((s, g, perfil))
    # Flush ANTES de los dependientes: `Guardian` y `StudentGroup` no declaran
    # `relationship` con `Student`, así que SQLAlchemy no conoce el orden de
    # inserción y mete los hijos primero — FK violada.
    await db.flush()

    for s, g, _ in estudiantes:
        gid = uuid4()
        guardianes[s.id] = gid
        db.add(Guardian(id=gid, student_id=s.id,
                        full_name=f"Acudiente de {s.first_name}",
                        relationship=random.choice(list(GuardianRelationship)),
                        email="pedrogomezl1805@gmail.com", phone="3000000000",
                        is_primary=True))
        db.add(StudentGroup(id=uuid4(), student_id=s.id, group_id=g.id,
                            academic_year=anio, is_active=True))
    await db.flush()
    print(f"  · {len(grupos)} salones, {len(estudiantes)} estudiantes")

    # --- Asistencia ---
    tasa_perfil = {"regular": 0.96, "intermitente": 0.86, "cronico": 0.62}
    filas_att, filas_tok, filas_just, filas_notif = [], [], [], []
    dias = dias_habiles(SEMANAS)
    for dia in dias:
        dow = dia.isoweekday()
        # Lunes y viernes concentran el ausentismo; es el patrón que la gráfica
        # "por día de la semana" tiene que revelar.
        ajuste_dia = -0.04 if dow in (1, 5) else 0.0
        for s, g, perfil in estudiantes:
            delbloque = [b for b in bloques[g.id] if b.day_of_week == dow]
            for cp in delbloque[:BLOQUES_CON_LISTA]:
                # Las últimas horas pierden gente: fuga de media jornada.
                ajuste_hora = -0.03 if cp.period_order >= 4 else 0.0
                p = tasa_perfil[perfil] + ajuste_dia + ajuste_hora
                x = random.random()
                if x < p:
                    estado = AttendanceStatus.LATE if random.random() < 0.06 else AttendanceStatus.PRESENT
                else:
                    estado = AttendanceStatus.ABSENT
                rid = uuid4()
                filas_att.append(dict(
                    id=rid, student_id=s.id, group_id=g.id, class_period_id=cp.id,
                    institution_id=INSTITUTION_ID, recorded_by_user_id=cp.user_id,
                    date=dia, status=estado,
                    created_at=datetime.combine(dia, cp.start_time),
                    absence_closed_at=None,
                ))
                # Solo la primera hora notifica al acudiente (regla del módulo).
                if estado == AttendanceStatus.ABSENT and cp.period_order == 1:
                    fallida = random.random() < 0.04
                    filas_notif.append(dict(
                        id=uuid4(), institution_id=INSTITUTION_ID, type=NotificationType.ABSENCE_FIRST_HOUR,
                        student_id=s.id, guardian_id=guardianes[s.id],
                        email_to="pedrogomezl1805@gmail.com",
                        subject=f"Inasistencia de {s.first_name}",
                        status=NotificationStatus.FAILED if fallida else NotificationStatus.SENT,
                        error_message="SMTP timeout" if fallida else None,
                        sent_at=None if fallida else datetime.combine(dia, time(8, 0)),
                        created_at=datetime.combine(dia, time(8, 0)),
                    ))
                    if not fallida and random.random() < 0.45:
                        tok = uuid4()
                        filas_tok.append(dict(
                            id=tok, attendance_record_id=rid, token=uuid4(),
                            expires_at=datetime.combine(dia, time(23, 59)) + timedelta(days=3),
                            used_at=datetime.combine(dia, time(18, 0)),
                            created_at=datetime.combine(dia, time(8, 0)),
                        ))
                        filas_just.append(dict(
                            id=uuid4(), attendance_record_id=rid, token_id=tok,
                            reason="Estuvo enfermo, adjunto incapacidad.",
                            submitted_at=datetime.combine(dia, time(18, 5)),
                            attachment_key=None, attachment_filename=None,
                            attachment_content_type=None, attachment_size_bytes=None,
                            archived_at=None,
                        ))

    for tabla, filas in ((AttendanceRecord, filas_att), (AttendanceToken, filas_tok),
                         (AttendanceJustification, filas_just), (NotificationLog, filas_notif)):
        for i in range(0, len(filas), 2000):     # por lotes: 20k filas en un execute
            await db.execute(insert(tabla), filas[i:i + 2000])
    print(f"  · {len(filas_att)} registros de asistencia, {len(filas_just)} justificaciones")

    # --- PAE ---
    inscritos = [e for e in estudiantes if random.random() < 0.65]
    enrollments = {}
    for s, _, _ in inscritos:
        enrolled_at = datetime.combine(dias[0], time(7, 0))
        e = PAEEnrollment(
            id=uuid4(), student_id=s.id, institution_id=INSTITUTION_ID, academic_year=anio,
            is_active=True, enrolled_at=enrolled_at,
            enrollment_hash=compute_enrollment_hash(s.id, INSTITUTION_ID, anio, enrolled_at),
        )
        db.add(e)
        enrollments[s.id] = e
    await db.flush()

    # Cuatro inscritos dejan de reclamar hace tres semanas: es el caso que la
    # vista de PAE debe sacar a la superficie (raciones perdidas / posible deserción).
    abandonan = {s.id for s, _, _ in inscritos[:4]}
    corte = dias[-1] - timedelta(days=21)
    filas_pae = []
    for dia in dias:
        for s, _, _ in inscritos:
            if s.id in abandonan and dia > corte:
                continue
            if random.random() > 0.88:
                continue
            created = datetime.combine(dia, time(9, 45))
            filas_pae.append(dict(
                id=uuid4(), student_id=s.id, institution_id=INSTITUTION_ID,
                delivered_by_user_id=PAE_USER_ID, delivery_date=dia,
                identification_method=PAEIdentificationMethod.DOCUMENT,
                delivery_hash=compute_delivery_hash(
                    student_id=s.id, delivery_date=dia, delivered_by_user_id=PAE_USER_ID,
                    created_at=created, enrollment_hash=enrollments[s.id].enrollment_hash),
                created_at=created,
            ))
    for i in range(0, len(filas_pae), 2000):
        await db.execute(insert(PAEDelivery), filas_pae[i:i + 2000])
    print(f"  · {len(inscritos)} inscritos al PAE, {len(filas_pae)} entregas")

    # --- Convivencia y salidas ---
    reincidentes = random.sample(estudiantes, 6)
    casos = []
    for _ in range(45):
        s, _, _ = random.choice(reincidentes if random.random() < 0.4 else estudiantes)
        casos.append((s, random.choice(dias)))
    n_art = 0
    for s, dia in casos:
        rid = uuid4()
        db.add(DisciplineRecord(
            id=rid, student_id=s.id, institution_id=INSTITUTION_ID,
            recorded_by_user_id=random.choice(docentes).id, date=dia,
            observations=random.choice(OBSERVACIONES),
            signature_url=f"signatures/demo/{rid}.png",
            created_at=datetime.combine(dia, time(11, 0)),
        ))
        if articulos:
            db.add(DisciplineRecordArticle(discipline_record_id=rid,
                                           article_id=random.choice(articulos)))
            n_art += 1
    for _ in range(35):
        s, _, _ = random.choice(estudiantes)
        dia = random.choice(dias)
        db.add(EarlyDeparture(
            id=uuid4(), student_id=s.id, institution_id=INSTITUTION_ID,
            recorded_by_user_id=random.choice(docentes).id, departure_date=dia,
            departure_time=time(random.randint(9, 11), random.choice([0, 15, 30])),
            reason=random.choice(MOTIVOS_SALIDA),
            created_at=datetime.combine(dia, time(10, 0)),
        ))
    await db.commit()
    print(f"  · {len(casos)} casos de convivencia ({n_art} con artículo), 35 salidas anticipadas")
    print(f"Listo. Período generado: {dias[0]} → {dias[-1]} ({len(dias)} días hábiles).")


async def main():
    async with AsyncSessionLocal() as db:
        if "--limpiar" in sys.argv:
            await limpiar(db)
            return
        await seed(db)


asyncio.run(main())
