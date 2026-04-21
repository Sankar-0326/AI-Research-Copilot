from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_copilot.db.models.user import User

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from research_copilot.db.database import Base


class APIKeyProvider(str, PyEnum):
    """Supported LLM/service providers."""
    openai   = "openai"
    pinecone = "pinecone"
    tavily   = "tavily"


class UserAPIKey(Base):
    __tablename__ = "user_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[APIKeyProvider] = mapped_column(
        Enum(APIKeyProvider),
        nullable=False,
    )
    encrypted_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    key_hint: Mapped[str] = mapped_column(
        # Last 4 chars of the original key — shown in UI only
        # Never enough to reconstruct the full key
        String(10),
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

    # Relationship back to user
    user: Mapped["User"] = relationship(
        "User",
        back_populates="api_keys",
    )

    def __repr__(self) -> str:
        return (
            f"<UserAPIKey provider={self.provider} "
            f"user_id={str(self.user_id)[:8]} "
            f"hint=...{self.key_hint}>"
        )