import enum
from datetime import datetime
from sqlalchemy import String, Float, ForeignKey, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .base import Base

class DealStatus(enum.Enum):
    # Этап 1: Оплата Тейкера (обычно Покупатель фиата)
    WAITING_BUYER_PAY = "waiting_buyer_pay"
    WAITING_SELLER_CONFIRM = "waiting_seller_confirm"
    
    # Этап 2: Оплата Мейкера (вторая сторона обмена)
    WAITING_SELLER_PAY = "waiting_seller_pay"
    WAITING_BUYER_CONFIRM = "waiting_buyer_confirm"
    
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"

class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    
    ad_id: Mapped[int | None] = mapped_column(ForeignKey("advertisements.id", ondelete="SET NULL"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    requisite_id: Mapped[int] = mapped_column(ForeignKey("user_requisites.id", ondelete="RESTRICT"))

    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.WAITING_BUYER_PAY)

    # Фиксируем суммы сделки
    amount_base: Mapped[float] = mapped_column(Float)   # Кол-во базовой валюты (напр. 1000 KRW)
    amount_quote: Mapped[float] = mapped_column(Float)  # Кол-во котируемой (напр. 72 RUB)
    
    # Два чека
    buyer_receipt_id: Mapped[str | None] = mapped_column(String(255))
    seller_receipt_id: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Срок жизни текущего шага (будет обновляться при переходе на новый этап оплаты)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))