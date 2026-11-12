from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    """Guruh modeli"""

    __tablename__ = "groups"
    __table_args__ = (
        Index("ix_groups_teacher_id", "teacher_id"),
        Index("ix_groups_center_id", "center_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    center_id: Mapped[int] = mapped_column(ForeignKey("centers.id"), nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
