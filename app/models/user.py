from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UserRole


class User(Base, TimestampMixin):
    """Foydalanuvchi modeli"""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_telegram_id", "telegram_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
