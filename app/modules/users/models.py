from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    center_id = Column(Integer, ForeignKey("centers.id"), nullable=False, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    telegram_username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'teacher', 'parent'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    center = relationship("Center", backref="users")
