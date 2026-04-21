from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_copilot.db.models.api_keys import UserAPIKey

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from research_copilot.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship — one user has many API keys
    api_keys: Mapped[list["UserAPIKey"]] = relationship(
        "UserAPIKey",
        back_populates="user",
        cascade="all, delete-orphan",   # deleting user deletes all their keys
        lazy="selectin",                # async-safe loading strategy
    )

    def __repr__(self) -> str:
        return f"<User id={str(self.id)[:8]} email={self.email}>"