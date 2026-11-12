from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Lesson(Base, TimestampMixin):
    """Dars modeli"""

    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("group_id", "lesson_date", name="uq_group_lesson_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False, index=True)
    lesson_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
