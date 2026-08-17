from datetime import date as PyDate, datetime, time
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import GuardianRelationship, UserRole
from app.schemas.guardian import GuardianCreate, GuardianResponse


def _strip_required(v: str) -> str:
    """Recorta y rechaza lo que quede vacío.

    `Field(min_length=1)` NO basta: los validadores corren **después** de las
    restricciones del Field, así que "   " pasa el min_length y luego un
    `.strip()` posterior lo deja en cadena vacía. Hay que comprobarlo aquí.
    """
    v = v.strip()
    if not v:
        raise ValueError("No puede estar vacío")
    return v


class AdminStats(BaseModel):
    # Generado para el día y semana actuales.
    date: PyDate

    # Población
    students_active: int
    staff_total: int
    teachers: int
    pae_operators: int

    # PAE
    pae_enrolled: int
    pae_delivered_today: int
    pae_delivered_week: int
    pae_claim_rate: float  # % de inscritos que reclamaron hoy (0-100)

    # Asistencia (hoy)
    attendance_present_today: int
    attendance_absent_today: int
    attendance_late_today: int
    attendance_justified_today: int
    attendance_rate_today: float  # % presentes+tardanzas sobre registros de hoy

    # Salidas tempranas (hoy)
    departures_today: int

    # Convivencia (infracciones por gravedad, histórico)
    discipline_records: int
    discipline_leve: int
    discipline_moderada: int
    discipline_grave: int

    # Notificaciones (histórico)
    notifications_sent: int
    notifications_failed: int
    notifications_pending: int


# ── Gestión: Personal (usuarios) ──────────────────────────────────────

# El admin no fija ni cambia contraseñas: al crear, el service genera una
# temporal y se la envía al usuario por correo; para cambiarla está el flujo
# público de `/auth/password-reset`. Por eso ni `AdminUserCreate` ni
# `AdminUserUpdate` aceptan `password` — si lo aceptaran, un admin podría fijar
# la contraseña de otra persona y entrar como ella.
class AdminUserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_number: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    role: UserRole


class AdminUserUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_number: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    role: UserRole


class AdminUserResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    document_number: str
    email: str
    role: UserRole
    is_active: bool
    photo_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Gestión: Académico ────────────────────────────────────────────────

class GradeResponse(BaseModel):
    id: UUID
    name: str
    level: int

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class SubjectUpdate(BaseModel):
    """Solo el nombre. `subject_id` no cambia, así que las asignaciones
    docente-salón que la referencian siguen apuntando a la misma materia."""
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class SubjectResponse(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    grade_id: UUID
    name: str = Field(min_length=1, max_length=10)
    academic_year: int = Field(ge=2000, le=2100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class GroupResponse(BaseModel):
    id: UUID
    grade_id: UUID
    grade_name: str | None = None
    grade_level: int | None = None
    name: str
    academic_year: int
    # Matrículas activas de estudiantes activos. Lo calcula el repo con un
    # subselect para no disparar una consulta por salón desde el front.
    student_count: int = 0

    model_config = {"from_attributes": True}


class GroupUpdate(BaseModel):
    """Solo el nombre. Cambiar de grado sería mover el salón entero — y con él
    el grado de todos sus matriculados —, que es otra operación distinta."""
    name: str = Field(min_length=1, max_length=10)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class GroupStudentAdd(BaseModel):
    student_id: UUID


class StudentGroupCreate(BaseModel):
    student_id: UUID
    group_id: UUID
    academic_year: int = Field(ge=2000, le=2100)


class StudentGroupResponse(BaseModel):
    id: UUID
    student_id: UUID
    group_id: UUID
    academic_year: int
    is_active: bool

    model_config = {"from_attributes": True}


# --- Alta completa de estudiante (estudiante + matrícula opcional + acudientes) ---

class AdminStudentCreate(BaseModel):
    document_number: str = Field(min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: PyDate
    # `student_groups` no tiene grade_id: el grado es un filtro de UI para acotar
    # el <select> de salón, nunca llega hasta acá.
    group_id: UUID | None = None
    # Inscribe al PAE del año vigente en la misma transacción del alta.
    is_pae_enrolled: bool = False
    guardians: list[GuardianCreate] = Field(min_length=1)

    @field_validator("document_number", "first_name", "last_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, v: PyDate) -> PyDate:
        if v > PyDate.today():
            raise ValueError("birth_date no puede estar en el futuro")
        return v

    @model_validator(mode="after")
    def exactly_one_primary(self) -> "AdminStudentCreate":
        if sum(1 for g in self.guardians if g.is_primary) != 1:
            raise ValueError("Debe haber exactamente un acudiente marcado como primario")
        return self


class AdminGuardianUpdate(BaseModel):
    # None = acudiente nuevo (se crea). Con valor = acudiente existente (se
    # actualiza in-place; nunca se borra y recrea, ver docs/students.md — un
    # acudiente puede tener notificaciones históricas con FK a su id).
    id: UUID | None = None
    full_name: str = Field(min_length=1, max_length=255)
    relationship: GuardianRelationship
    email: EmailStr = Field(max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    is_primary: bool = False

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class AdminStudentUpdate(BaseModel):
    document_number: str = Field(min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: PyDate
    group_id: UUID | None = None
    is_pae_enrolled: bool = False
    guardians: list[AdminGuardianUpdate] = Field(min_length=1)

    @field_validator("document_number", "first_name", "last_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, v: PyDate) -> PyDate:
        if v > PyDate.today():
            raise ValueError("birth_date no puede estar en el futuro")
        return v

    @model_validator(mode="after")
    def exactly_one_primary(self) -> "AdminStudentUpdate":
        if sum(1 for g in self.guardians if g.is_primary) != 1:
            raise ValueError("Debe haber exactamente un acudiente marcado como primario")
        return self


class AdminStudentDetailResponse(BaseModel):
    id: UUID
    document_number: str
    first_name: str
    last_name: str
    birth_date: PyDate
    photo_url: str | None
    is_active: bool
    grade_id: UUID | None = None
    grade_name: str | None = None
    group_id: UUID | None = None
    group_name: str | None = None
    is_pae_enrolled: bool
    guardians: list[GuardianResponse]

    model_config = {"from_attributes": True}


# ── Gestión: Horarios ─────────────────────────────────────────────────

class _ClassPeriodFields(BaseModel):
    """Campos comunes de un bloque. `name` es la etiqueta ("Primera hora",
    "Descanso"); la materia va en `subject_id`, del catálogo. Antes se usaba
    `name` para ambas cosas y ya divergía del catálogo.

    **No lleva `period_order`.** Un bloque se define por su hora de inicio y de
    fin, y el orden se deriva de ahí (ver `_renumber_day` en el service): que el
    admin pudiera elegirlo permitía un orden 2 que empezaba antes que el orden 1.
    Tampoco lleva `span`: la duración es `end_time - start_time` y nada más.
    """
    name: str = Field(min_length=1, max_length=100)
    start_time: time
    end_time: time
    subject_id: UUID | None = None
    # Obligatorio: todo bloque tiene docente. Ver el modelo y la migración
    # `d6c1f8a390b4` — sin docente nadie toma lista en ese bloque.
    user_id: UUID

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)

    @model_validator(mode="after")
    def end_after_start(self):
        # Duplica el CHECK de la BD para dar 422 con mensaje en vez de un 500.
        if self.start_time >= self.end_time:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        return self


class ClassPeriodCreate(_ClassPeriodFields):
    group_id: UUID
    day_of_week: int = Field(ge=1, le=7)


class ClassPeriodUpdate(_ClassPeriodFields):
    """No incluye `group_id`: mover un bloque de salón es recolocarlo, no
    editarlo. `day_of_week` sí es opcionalmente editable — arrastrar una clase
    del martes al jueves es una edición legítima, y al derivarse el orden ya no
    hay ningún `UNIQUE(group, orden, día)` que esquivar: los dos días afectados
    se renumeran."""
    day_of_week: int | None = Field(default=None, ge=1, le=7)


class ClassPeriodResponse(BaseModel):
    id: UUID
    group_id: UUID
    name: str
    # Derivado por el service, no enviado por el cliente. Se devuelve porque la
    # UI marca cuál es la primera hora (la que notifica al acudiente).
    period_order: int
    start_time: time
    end_time: time
    day_of_week: int
    subject_id: UUID | None = None
    subject_name: str | None = None
    user_id: UUID | None = None
    teacher_name: str | None = None

    model_config = {"from_attributes": True}


# ── Gestión: PAE (inscritos) ──────────────────────────────────────────

class PAEEnrollmentAdd(BaseModel):
    """Inscribir a un estudiante **ya existente**. Solo el id: el año académico
    es el vigente y `enrolled_at` lo pone el servidor, porque ambos entran en el
    `enrollment_hash` (capa 1 de la cadena de integridad del PAE) y aceptarlos
    del cliente permitiría fabricar una inscripción con fecha elegida."""
    student_id: UUID


class PAEEnrollmentItem(BaseModel):
    """Fila del listado de inscritos. Lleva los datos del estudiante ya
    resueltos (nombre, salón, foto) para que la consola no tenga que pedir el
    detalle uno por uno."""
    student_id: UUID
    document_number: str
    first_name: str
    last_name: str
    photo_url: str | None = None
    grade_name: str | None = None
    group_name: str | None = None
    academic_year: int
    enrolled_at: datetime
    is_active: bool
    student_is_active: bool
    # Última ración reclamada, para distinguir de un vistazo al inscrito que
    # usa el programa del que se inscribió y nunca apareció.
    last_delivery: PyDate | None = None


class PAEEnrollmentSummary(BaseModel):
    activos: int
    inactivos: int
    sin_reclamar_nunca: int
    academic_year: int
    items: list[PAEEnrollmentItem]


class UserGroupCreate(BaseModel):
    user_id: UUID
    group_id: UUID
    academic_year: int = Field(ge=2000, le=2100)
    subject_id: UUID | None = None


class UserGroupResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str | None = None
    group_id: UUID
    academic_year: int
    subject_id: UUID | None = None
    subject_name: str | None = None

    model_config = {"from_attributes": True}
