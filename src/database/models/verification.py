import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .base import Base

if TYPE_CHECKING:
    from .user import User

class VerificationStatus(enum.Enum):
    PENDING = "pending"     # Заявка подана пользователем
    ACTIVE = "active"       # Админ начал диалог, создан топик
    COMPLETED = "completed" # Верификация успешно пройдена
    DECLINED = "declined"   # В верификации отказано

class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    group_topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="verification_request")
