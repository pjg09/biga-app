from app.core.database import Base  # noqa: F401

from app.models.institution import Institution  # noqa: F401
from app.models.grade import Grade  # noqa: F401
from app.models.group import Group  # noqa: F401
from app.models.class_period import ClassPeriod  # noqa: F401
from app.models.subject import Subject  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_group import UserGroup  # noqa: F401
from app.models.student import Student  # noqa: F401
from app.models.student_group import StudentGroup  # noqa: F401
from app.models.guardian import Guardian  # noqa: F401
from app.models.pae import PAEEnrollment, PAEDelivery  # noqa: F401
from app.models.attendance import (  # noqa: F401
    AttendanceAbsenceNote,
    AttendanceRecord,
    AttendanceToken,
    AttendanceJustification,
    AttendanceJustificationNote,
)
from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord, DisciplineRecordArticle  # noqa: F401
from app.models.departure import EarlyDeparture  # noqa: F401
from app.models.notification import NotificationLog  # noqa: F401
from app.models.import_job import ImportJob  # noqa: F401
from app.models.lead import DemoLead  # noqa: F401
from app.models.password_reset import PasswordResetOTP  # noqa: F401
