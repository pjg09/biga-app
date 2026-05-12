import enum


class UserRole(str, enum.Enum):
    TEACHER = "TEACHER"
    PAE_OPERATOR = "PAE_OPERATOR"


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
    ABSENCE_FIRST_HOUR = "ABSENCE_FIRST_HOUR"
    DISCIPLINE_RECORD = "DISCIPLINE_RECORD"
    EARLY_DEPARTURE = "EARLY_DEPARTURE"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class ImportJobType(str, enum.Enum):
    STUDENTS = "STUDENTS"
    PAE_ENROLLMENT = "PAE_ENROLLMENT"
    CONVIVENCIA_ARTICLES = "CONVIVENCIA_ARTICLES"


class ImportJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
