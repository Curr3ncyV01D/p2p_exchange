from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.deal import Deal, DealStatus

class DealRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_deal(
        self, 
        ad_id: int, 
        public_id: str, 
        buyer_id: int, 
        seller_id: int, 
        requisite_id: int, 
        amount_base: float, 
        amount_quote: float, 
    ) -> Deal:
        """Создает новую сделку с универсальными валютными полями"""
        
        # Устанавливаем таймер на 15 минут от текущего момента
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        new_deal = Deal(
            ad_id=ad_id,
            public_id=public_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            requisite_id=requisite_id,
            amount_base=amount_base,
            amount_quote=amount_quote,
            status=DealStatus.WAITING_BUYER_PAY,
            expires_at=expires_at
        )
        
        self.session.add(new_deal)
        await self.session.commit()
        await self.session.refresh(new_deal)
        return new_deal

    async def get_deal_by_id(self, deal_id: int) -> Deal | None:
        result = await self.session.execute(select(Deal).where(Deal.id == deal_id))
        return result.scalar_one_or_none()

    async def get_deal_by_public_id(self, public_id: str) -> Deal | None:
        result = await self.session.execute(
            select(Deal).where(Deal.public_id == public_id)
        )
        return result.scalar_one_or_none()

    async def update_deal(self, public_id: str, **kwargs):
        """Универсальный метод для обновления полей сделки"""
        query = update(Deal).where(Deal.public_id == public_id).values(**kwargs)
        await self.session.execute(query)
        await self.session.commit()
    
    async def get_active_deals_by_user(self, user_id: int):
        """Получить все незавершенные сделки, где участвует пользователь"""
        from sqlalchemy import or_
        query = (
            select(Deal)
            .where(
                or_(Deal.buyer_id == user_id, Deal.seller_id == user_id),
                Deal.status.not_in([DealStatus.COMPLETED, DealStatus.CANCELLED])
            )
            .order_by(Deal.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()