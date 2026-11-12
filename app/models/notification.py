from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, NotificationStatus, TimestampMixin


class Notification(Base, TimestampMixin):
    """Ota-ona xabarlari"""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("attendance_id", "parent_user_id", name="uq_attendance_parent"),
        Index("ix_notifications_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(
        ForeignKey("attendance.id"), nullable=False, index=True
    )
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[NotificationStatus] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
