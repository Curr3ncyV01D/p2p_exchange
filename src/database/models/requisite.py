from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

class UserRequisite(Base):
    __tablename__ = "user_requisites"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    
    bank_name: Mapped[str] = mapped_column(String(50))  # Название банка (Сбербанк, Woori)
    details: Mapped[str] = mapped_column(String(255))   # Сами реквизиты (номер карты, телефон)
    
    user: Mapped["User"] = relationship(back_populates="requisites")