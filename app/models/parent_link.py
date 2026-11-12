from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ParentLink(Base, TimestampMixin):
    """Ota-ona va o'quvchi bog'lanishi"""

    __tablename__ = "parent_links"
    __table_args__ = (Index("ix_parent_links_student_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    invite_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
