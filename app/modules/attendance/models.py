from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.db import Base


class AttendanceSubmission(Base):
    __tablename__ = "attendance_submissions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_idempotency_key"),)

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    teacher = relationship("User", backref="attendance_submissions")
    lesson = relationship("Lesson", backref="attendance_submissions")
