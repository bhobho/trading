"""
models/user.py — SQLAlchemy ORM model for application users.
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # "admin" or "user"
    role = Column(String(16), nullable=False, default="user")

    # Soft-delete: set is_active=False instead of hard-deleting to preserve trade history
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    def is_admin(self) -> bool:
        return self.role == "admin"
