from sqlalchemy import BigInteger, String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from .base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    display_name: Mapped[str] = mapped_column(String(50), unique=True)  # Анонимное имя на площадке
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    deal_count: Mapped[int] = mapped_column(default=0)

    is_admin: Mapped[bool] = mapped_column(default=False)
    is_verified: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)

    conflict_strikes: Mapped[int] = mapped_column(default=0)  # Счетчик штрафов

    requisites: Mapped[List["UserRequisite"]] = relationship(back_populates="user", cascade="all, delete-orphan")