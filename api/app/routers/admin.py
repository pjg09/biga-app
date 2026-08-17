from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.database import get_db
from app.core.dependencies import get_storage_adapter, require_admin
from app.models.user import User
from app.repositories.admin_management_repository import AdminManagementRepository
from app.repositories.admin_repository import AdminRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.pae_repository import PAERepository
from app.repositories.stats_repository import StatsRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.admin import (
    AdminStats,
    AdminStudentCreate,
    AdminStudentDetailResponse,
    AdminStudentUpdate,
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    ClassPeriodCreate,
    ClassPeriodUpdate,
    ClassPeriodResponse,
    GradeResponse,
    GroupCreate,
    GroupStudentAdd,
    GroupUpdate,
    GroupResponse,
    PAEEnrollmentAdd,
    PAEEnrollmentItem,
    PAEEnrollmentSummary,
    StudentGroupCreate,
    StudentGroupResponse,
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    UserGroupCreate,
    UserGroupResponse,
)
from app.schemas.stats import (
    AttendanceStats,
    DisciplineStats,
    OverviewStats,
    PAEStats,
    RiskStats,
)
from app.schemas.students import StudentResponse
from app.services.admin_management_service import AdminManagementService
from app.services.admin_service import AdminService
from app.services.stats_service import StatsService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(AdminRepository(db))


def get_mgmt_service(
    db: AsyncSession = Depends(get_db),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
) -> AdminManagementService:
    return AdminManagementService(
        AdminManagementRepository(db), StudentRepository(db), GuardianRepository(db),
        PAERepository(db), storage,
    )


def get_stats_service(db: AsyncSession = Depends(get_db)) -> StatsService:
    return StatsService(StatsRepository(db), AdminRepository(db))


# --- Estadísticas ---

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    current_user: User = Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    """Foto del día, la que alimenta el Resumen del dashboard. Las series
    históricas y los cruces por salón/estudiante viven en `/stats/*`."""
    return await service.get_stats(institution_id=current_user.institution_id)


# Ventanas ofrecidas. Cerrada a propósito en vez de aceptar cualquier entero:
# un `days=100000` recorre la tabla de asistencia entera por gusto, y el front
# no ofrece nada fuera de esta lista.
_DIAS = Query(default=30, description="Ventana en días", ge=7, le=365)


@router.get("/stats/overview", response_model=OverviewStats)
async def stats_overview(
    days: int = _DIAS,
    current_user: User = Depends(require_admin),
    service: StatsService = Depends(get_stats_service),
):
    """KPIs con variación contra el período anterior + alertas accionables."""
    return await service.overview(current_user.institution_id, days)


@router.get("/stats/attendance", response_model=AttendanceStats)
async def stats_attendance(
    days: int = _DIAS,
    current_user: User = Depends(require_admin),
    service: StatsService = Depends(get_stats_service),
):
    return await service.attendance(current_user.institution_id, days)


@router.get("/stats/pae", response_model=PAEStats)
async def stats_pae(
    days: int = _DIAS,
    current_user: User = Depends(require_admin),
    service: StatsService = Depends(get_stats_service),
):
    return await service.pae(current_user.institution_id, days)


@router.get("/stats/discipline", response_model=DisciplineStats)
async def stats_discipline(
    days: int = _DIAS,
    current_user: User = Depends(require_admin),
    service: StatsService = Depends(get_stats_service),
):
    return await service.discipline(current_user.institution_id, days)


@router.get("/stats/risk", response_model=RiskStats)
async def stats_risk(
    days: int = _DIAS,
    current_user: User = Depends(require_admin),
    service: StatsService = Depends(get_stats_service),
):
    """Estudiantes ordenados por señales de riesgo (ausentismo, convivencia,
    salidas, PAE sin reclamar). Es la vista que se usa para decidir a quién
    llamar, así que devuelve nombre y documento — no es anónima a propósito."""
    return await service.risk(current_user.institution_id, days)


# --- PAE: inscritos (consola de gestión) ---

@router.get("/pae/enrollments", response_model=PAEEnrollmentSummary)
async def list_pae_enrollments(
    include_inactive: bool = Query(
        False, description="Incluir inscripciones dadas de baja (para reactivarlas)"
    ),
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Inscritos al PAE del año en curso, con salón y última ración reclamada.

    Solo ADMIN, igual que `POST /pae/enrollments`: el operador del PAE *opera* el
    programa pero no decide quién entra (ver `docs/pae.md`)."""
    return await service.list_pae_enrollments(
        current_user.institution_id, include_inactive=include_inactive
    )


@router.post("/pae/enrollments", response_model=PAEEnrollmentItem,
             status_code=status.HTTP_201_CREATED)
async def add_pae_enrollment(
    body: PAEEnrollmentAdd,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Inscribe a un estudiante ya existente, o reactiva su inscripción si la
    tuvo dada de baja. **No** duplica la fila: `enrolled_at` y el hash de la
    inscripción son la capa 1 de la cadena de integridad del PAE.

    Se diferencia de `POST /pae/enrollments` (módulo PAE), que responde 409 ante
    cualquier inscripción existente del año — semántica correcta para un alta
    puntual, inservible para una consola donde reinscribir es una operación
    normal."""
    return await service.add_pae_enrollment(body, current_user.institution_id)


@router.delete("/pae/enrollments/{student_id}", response_model=PAEEnrollmentItem)
async def deactivate_pae_enrollment(
    student_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Baja lógica: el estudiante deja de aparecer en el listado del día del
    operador. **No borra la inscripción** — las entregas ya registradas encadenan
    su hash con el de ella y borrarla rompería la auditoría."""
    return await service.set_pae_enrollment_active(
        student_id, current_user.institution_id, active=False
    )


@router.post("/pae/enrollments/{student_id}/reactivate", response_model=PAEEnrollmentItem)
async def reactivate_pae_enrollment(
    student_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.set_pae_enrollment_active(
        student_id, current_user.institution_id, active=True
    )


# --- Personal (usuarios) ---

@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminUserCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_user(body, current_user.institution_id)


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    include_inactive: bool = Query(
        False, description="Incluir usuarios desactivados (para poder reactivarlos)"
    ),
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_users(current_user.institution_id, include_inactive=include_inactive)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user_detail(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Ficha de detalle para la consola de admin. No colisiona con ninguna ruta
    estática bajo /admin/users (no existe un /admin/users/search)."""
    return await service.get_user_detail(user_id, current_user.institution_id)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: UUID,
    body: AdminUserUpdate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Contraparte de `POST /users` para editar un miembro del personal ya
    existente. No incluye contraseña: el admin no puede fijar la de otra
    persona (ver `AdminUserCreate`/`AdminUserUpdate` en `schemas/admin.py`).

    `409` si un admin intenta quitarse a sí mismo el rol de administrador: es el
    mismo autobloqueo que cubre `DELETE /users/{id}`, por otra vía."""
    return await service.update_user(
        user_id, body, current_user.institution_id, current_user_id=current_user.id
    )


@router.delete("/users/{user_id}", response_model=AdminUserResponse)
async def deactivate_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Baja lógica: apaga `is_active`. **No borra la fila** — el histórico que
    ese usuario firmó debe seguir siendo trazable. Revoca el acceso de inmediato
    porque `get_current_user` valida `is_active` en cada request.

    `409` si el admin intenta desactivarse a sí mismo o dejar la institución sin
    ningún administrador activo."""
    return await service.set_user_active(
        user_id, current_user.institution_id, active=False, current_user_id=current_user.id
    )


@router.post("/users/{user_id}/reactivate", response_model=AdminUserResponse)
async def reactivate_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.set_user_active(
        user_id, current_user.institution_id, active=True, current_user_id=current_user.id
    )


@router.post("/users/{user_id}/photo", response_model=AdminUserResponse)
async def upload_user_photo(
    user_id: UUID,
    photo: UploadFile = File(..., description="Foto del miembro del personal (JPG, PNG o WEBP)"),
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Sube la foto de un miembro del personal a object storage.

    Multipart, igual que `POST /students/{id}/photo`. Va después de
    `PUT /users/{user_id}` en el archivo, pero no compite con él: distinto
    método y un segmento extra."""
    data = await photo.read()
    return await service.set_user_photo(
        user_id=user_id,
        institution_id=current_user.institution_id,
        data=data,
        content_type=photo.content_type or "",
    )


# --- Académico: grados (solo lectura) ---
#
# No hay `POST /grades`: los grados son un catálogo fijo de 11 niveles sembrado
# en la BD por la migración `a7c3e9f2b581`. Ver `app/core/grades.py`.

@router.get("/grades", response_model=list[GradeResponse])
async def list_grades(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_grades(current_user.institution_id)


# --- Académico: materias (catálogo) ---

@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    body: SubjectCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_subject(body, current_user.institution_id)


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
async def rename_subject(
    subject_id: UUID,
    body: SubjectUpdate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Renombra la materia. Solo la etiqueta: `subject_id` no cambia, así que
    las asignaciones docente-salón la siguen referenciando. `409` si ya existe
    otra materia con ese nombre en la institución."""
    return await service.rename_subject(subject_id, body.name, current_user.institution_id)


@router.get("/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_subjects(current_user.institution_id)


# --- Académico: grupos ---

@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_group(body, current_user.institution_id)


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_groups(current_user.institution_id)


# --- Académico: matrícula estudiante-grupo ---

@router.put("/groups/{group_id}", response_model=GroupResponse)
async def rename_group(
    group_id: UUID,
    body: GroupUpdate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Renombra el salón. Solo el nombre: cambiar de grado movería a todos sus
    matriculados de grado, que es otra operación. `409` si ya hay un salón con
    ese nombre en el mismo grado y año."""
    return await service.rename_group(group_id, body.name, current_user.institution_id)


@router.post("/groups/{group_id}/students", response_model=StudentGroupResponse,
             status_code=status.HTTP_201_CREATED)
async def add_student_to_group(
    group_id: UUID,
    body: GroupStudentAdd,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Mete a un estudiante en el salón, **moviéndolo** si ya estaba en otro.

    `student_groups` es único por (estudiante, año), así que agregar y mover son
    la misma operación. `409` solo si ya estaba en este mismo salón."""
    return await service.add_student_to_group(group_id, body.student_id, current_user.institution_id)


@router.delete("/groups/{group_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_student_from_group(
    group_id: UUID,
    student_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Saca al estudiante del salón (`is_active = False`). No borra la matrícula:
    es el histórico de en qué salón estuvo ese año."""
    await service.remove_student_from_group(group_id, student_id, current_user.institution_id)


@router.post("/student-groups", response_model=StudentGroupResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student_in_group(
    body: StudentGroupCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.enroll_student_in_group(body, current_user.institution_id)


# --- Alta completa de estudiante (estudiante + matrícula opcional + acudientes) ---

@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student_full(
    body: AdminStudentCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Distinto de `POST /students` (bare, sin restricción de rol): este crea
    Student + matrícula opcional + Guardians en una sola transacción atómica."""
    return await service.create_student_full(body, current_user.institution_id)


@router.get("/students/{student_id}", response_model=AdminStudentDetailResponse)
async def get_student_detail(
    student_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Ficha de detalle + datos para precargar el formulario de edición
    (`group_id`/`guardians[].id` en crudo, no solo nombres). Declarado después
    de `POST /students` en el archivo; no colisiona con ninguna ruta estática
    bajo `/students` (a diferencia de `GET /students/{id}` en `routers/students.py`,
    acá no existe un `/admin/students/search` con el que pisarse)."""
    return await service.get_student_detail(student_id, current_user.institution_id)


@router.put("/students/{student_id}", response_model=AdminStudentDetailResponse)
async def update_student_full(
    student_id: UUID,
    body: AdminStudentUpdate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Edita Student + matrícula del año vigente + Guardians + inscripción PAE
    en una sola transacción atómica — la contraparte de `POST /students` para
    modificar un estudiante ya existente."""
    return await service.update_student_full(student_id, body, current_user.institution_id)


@router.delete("/students/{student_id}", response_model=StudentResponse)
async def deactivate_student(
    student_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Baja lógica: apaga `is_active`. **No borra la fila** — agendatorio,
    asistencia, justificaciones y entregas del PAE siguen apuntando a este
    `student_id` y el histórico queda intacto. Deja de aparecer en listados,
    búsqueda y rosters porque todas esas consultas ya filtran `is_active`."""
    return await service.set_student_active(student_id, current_user.institution_id, active=False)


@router.post("/students/{student_id}/reactivate", response_model=StudentResponse)
async def reactivate_student(
    student_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.set_student_active(student_id, current_user.institution_id, active=True)


# --- Horarios: bloques (class_periods) ---

@router.post("/class-periods", response_model=ClassPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_class_period(
    body: ClassPeriodCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.create_class_period(body, current_user.institution_id)


@router.put("/class-periods/{cp_id}", response_model=ClassPeriodResponse)
async def update_class_period(
    cp_id: UUID,
    body: ClassPeriodUpdate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Edita un bloque: etiqueta, horas, materia, docente y —opcionalmente— día.
    No cambia de salón: eso sí es recolocarlo. El `period_order` no se envía,
    lo deriva el service de la hora de inicio."""
    return await service.update_class_period(cp_id, body, current_user.institution_id)


@router.delete("/class-periods/{cp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class_period(
    cp_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    """Borra el bloque. `409` si ya tiene asistencia tomada — esos registros son
    histórico y su FK apunta aquí."""
    await service.delete_class_period(cp_id, current_user.institution_id)


@router.get("/class-periods", response_model=list[ClassPeriodResponse])
async def list_class_periods(
    group_id: UUID,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_class_periods(group_id, current_user.institution_id)


# --- Horarios: asignación docente-grupo ---

@router.post("/teacher-assignments", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED)
async def assign_teacher(
    body: UserGroupCreate,
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.assign_teacher(body, current_user.institution_id)


@router.get("/teacher-assignments", response_model=list[UserGroupResponse])
async def list_teacher_assignments(
    current_user: User = Depends(require_admin),
    service: AdminManagementService = Depends(get_mgmt_service),
):
    return await service.list_teacher_assignments(current_user.institution_id)
