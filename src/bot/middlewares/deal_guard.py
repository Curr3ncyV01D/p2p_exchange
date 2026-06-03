from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from src.database.repository.deal_repo import DealRepository
from src.database.models.deal import DealStatus

class DealGuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # 1. Проверяем, есть ли в callback_data упоминание сделки
        # Мы договорились, что в сделках callback всегда содержит public_id
        # Например: maker_confirm_{public_id}, taker_confirm_{public_id}
        
        callback_data = event.data
        if not any(prefix in callback_data for prefix in ["maker_confirm_", "taker_confirm_", "deal_paid_", "dispute_"]):
            return await handler(event, data)

        # 2. Извлекаем public_id (он всегда последний элемент после разбивки по '_')
        deal_public_id = callback_data.split("_")[-1]
        
        # 3. Достаем сделку через репозиторий
        db_session = data["db_session"]
        deal_repo = DealRepository(db_session)
        deal = await deal_repo.get_deal_by_public_id(deal_public_id)

        if not deal:
            return await event.answer("❌ Сделка не найдена", show_alert=True)

        # 4. ПРОВЕРКА СТАТУСА: Если сделка уже закрыта или в споре — блокируем выполнение хендлера
        if deal.status in [DealStatus.COMPLETED, DealStatus.CANCELLED, DealStatus.DISPUTED]:
            if deal.status == DealStatus.DISPUTED:
                warning_text = f"⚖️ Эта сделка (#{deal.public_id}) находится в состоянии спора. Дождитесь решения Арбитра."
            else:
                warning_text = f"⚠️ Эта сделка (#{deal.public_id}) уже завершена или отменена."
            
            # Универсальная логика редактирования
            try:
                # Если у сообщения есть photo, document или video - редактируем caption
                if event.message.photo or event.message.document or event.message.video:
                    await event.message.edit_caption(caption=warning_text, reply_markup=None)
                else:
                    # Если это обычное текстовое сообщение - редактируем text
                    await event.message.edit_text(text=warning_text, reply_markup=None)
            except TelegramBadRequest:
                # На случай если сообщение нельзя редактировать (например, прошло > 48 часов)
                pass
            
            return await event.answer("Действие заблокировано", show_alert=True)

        # 5. Пробрасываем объект deal дальше
        # Теперь в хендлере можно будет написать (callback, deal: Deal)
        data["active_deal"] = deal
        
        return await handler(event, data)