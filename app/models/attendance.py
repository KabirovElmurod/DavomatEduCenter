from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AttendanceStatus, Base, TimestampMixin


class Attendance(Base, TimestampMixin):
    """Davomat modeli"""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("lesson_id", "student_id", name="uq_lesson_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(nullable=False)
