from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.db import Base


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (Index("ix_lessons_group_date", "group_id", "lesson_date"),)

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    lesson_date = Column(DateTime(timezone=True), nullable=False)
    topic = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    group = relationship("Group", backref="lessons")
    attendances = relationship("Attendance", back_populates="lesson")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("lesson_id", "student_id", name="uq_lesson_student"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False)  # 'present', 'absent', 'late'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    lesson = relationship("Lesson", back_populates="attendances")
    student = relationship("Student", backref="attendances")
