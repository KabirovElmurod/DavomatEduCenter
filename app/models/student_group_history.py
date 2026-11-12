from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StudentGroupHistory(Base, TimestampMixin):
    """O'quvchi guruh ko'chirish tarixi"""

    __tablename__ = "student_group_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)
    from_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
