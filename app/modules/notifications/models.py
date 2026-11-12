from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.db import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("attendance_id", "parent_user_id", name="uq_attendance_parent"),
        Index("ix_notifications_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=False, index=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False)  # 'pending', 'sent', 'failed', 'blocked'
    error_message = Column(String(1000), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    attendance = relationship("Attendance", backref="notifications")
    parent = relationship("User", backref="notifications")
