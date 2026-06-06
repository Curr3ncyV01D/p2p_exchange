import enum
from sqlalchemy import String, Float, ForeignKey, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Currency(enum.Enum):
    RUB = "RUB"
    KRW = "KRW"
    KZT = "KZT"

class AdStatus(enum.Enum):
    ACTIVE = "active"     # Видно в маркете
    PENDING = "pending"   # Покупатель отправл запрос на сделку
    HIDDEN = "hidden"     # Скрыто пользователем вручную
    ARCHIVED = "archived" # Удалено/Архивировано

class Ad(Base):
    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    requisite_id: Mapped[int] = mapped_column(ForeignKey("user_requisites.id", ondelete="RESTRICT"))
    
    # Мультивалютность
    base_currency: Mapped[Currency] = mapped_column(Enum(Currency))   # Что меняем
    quote_currency: Mapped[Currency] = mapped_column(Enum(Currency))  # На что
    
    # Лимиты
    min_limit: Mapped[float] = mapped_column(Float)
    max_limit: Mapped[float] = mapped_column(Float)
    rate: Mapped[float] = mapped_column(Float)
    
    bank: Mapped[str] = mapped_column(String(50))
    is_verified_only: Mapped[bool] = mapped_column(default=False)
    status: Mapped[AdStatus] = mapped_column(Enum(AdStatus), default=AdStatus.ACTIVE)