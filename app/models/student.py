from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Student(Base, TimestampMixin):
    """O'quvchi modeli"""

    __tablename__ = "students"
    __table_args__ = (
        Index("ix_students_group_id", "group_id"),
        Index("ix_students_center_id_is_active", "center_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    center_id: Mapped[int] = mapped_column(ForeignKey("centers.id"), nullable=False, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
