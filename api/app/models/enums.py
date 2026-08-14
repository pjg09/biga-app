import enum


class UserRole(str, enum.Enum):
    TEACHER = "TEACHER"
    PAE_OPERATOR = "PAE_OPERATOR"
    ADMIN = "ADMIN"


class GuardianRelationship(str, enum.Enum):
    PADRE = "PADRE"
    MADRE = "MADRE"
    ACUDIENTE = "ACUDIENTE"
    OTRO = "OTRO"


class PAEIdentificationMethod(str, enum.Enum):
    DOCUMENT = "DOCUMENT"
    FACIAL = "FACIAL"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    JUSTIFIED = "JUSTIFIED"


class ArticleSeverity(str, enum.Enum):
    LEVE = "LEVE"
    MODERADA = "MODERADA"
    GRAVE = "GRAVE"


class NotificationType(str, enum.Enum):
    PAE_NO_CLAIM = "PAE_NO_CLAIM"
    PAE_LATE_CLAIM_CORRECTION = "PAE_LATE_CLAIM_CORRECTION"
    ABSENCE_FIRST_HOUR = "ABSENCE_FIRST_HOUR"
    DISCIPLINE_RECORD = "DISCIPLINE_RECORD"
    EARLY_DEPARTURE = "EARLY_DEPARTURE"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    # No se intentó enviar a propósito (ej. lead duplicado dentro de la ventana
    # de 24h). Distinto de PENDING, que significa "encolado, aún sin resolver".
    SUPPRESSED = "SUPPRESSED"


class ImportJobType(str, enum.Enum):
    STUDENTS = "STUDENTS"
    PAE_ENROLLMENT = "PAE_ENROLLMENT"
    CONVIVENCIA_ARTICLES = "CONVIVENCIA_ARTICLES"


class ImportJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
