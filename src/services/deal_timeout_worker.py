from aiogram import Bot
from src.bot.instance import get_bot
from src.database.session import async_session
from src.database.models.deal import Deal, DealStatus
from src.database.models.ad import Ad, AdStatus
from sqlalchemy import select, update

async def check_deal_timeout(deal_id: int, public_id: str):
    bot = get_bot()
    async with async_session() as session:
        # 1. Проверяем статус сделки
        result = await session.execute(select(Deal).where(Deal.id == deal_id))
        deal = result.scalar_one_or_none()

        if not deal or deal.status not in [DealStatus.WAITING_BUYER_PAY, DealStatus.WAITING_SELLER_PAY]:
            return # Сделка уже либо оплачена, либо отменена

        # 2. Если статус всё еще OPEN — отменяем сделку
        deal.status = DealStatus.CANCELLED
        
        # 3. Возвращаем объявление в маркет
        await session.execute(
            update(Ad)
            .where(Ad.id == deal.ad_id)
            .values(status=AdStatus.ACTIVE)
        )
        
        await session.commit()

        # 4. Уведомляем участников
        try:
            await bot.send_message(
                deal.buyer_id, 
                f"⚠️ Время оплаты сделки #{public_id} истекло (15 мин).\nСделка отменена."
            )
            await bot.send_message(
                deal.seller_id, 
                f"⚠️ Покупатель не оплатил сделку #{public_id} вовремя.\nОбъявление возвращено в маркет."
            )
        except Exception:
            pass # Юзер мог заблокировать бота