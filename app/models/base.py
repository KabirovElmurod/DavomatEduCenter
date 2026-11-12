from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """created_at va updated_at maydonlari uchun mixin"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class UserRole(StrEnum):
    """User rollari"""

    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    ADMIN = "admin"
    TEACHER = "teacher"
    PARENT = "parent"


class AttendanceStatus(StrEnum):
    """Davomat holatlari"""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class NotificationStatus(StrEnum):
    """Xabar holatlari"""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BLOCKED = "blocked"


class AuditAction(StrEnum):
    """Audit log action turlari"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"
    RESTORE = "restore"
    TRANSFER = "transfer"
