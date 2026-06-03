from sqlalchemy import BigInteger, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from .base import Base

class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), unique=True)
    opened_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # ID темы в супергруппе админов
    group_topic_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    
    status: Mapped[str] = mapped_column(String(20), default="open") # open, closed
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relations
    deal: Mapped["Deal"] = relationship()
    opened_by: Mapped["User"] = relationship()