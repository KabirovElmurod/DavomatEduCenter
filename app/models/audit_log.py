from sqlalchemy import JSON, BigInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditAction, Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    """Audit log"""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_center_id_created_at", "center_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    center_id: Mapped[int] = mapped_column(ForeignKey("centers.id"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(nullable=False)
    entity: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    old: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new: Mapped[dict | None] = mapped_column(JSON, nullable=True)
