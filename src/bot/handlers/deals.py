from datetime import datetime, timedelta, timezone
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states.deals import DealStates
from src.bot.keyboards.deals import DealKeyboards
from src.bot.keyboards.review import ReviewKeyboards
from src.database.repository.ad_repo import AdRepository
from src.database.repository.deal_repo import DealRepository
from src.database.repository.user_repo import UserRepository
from src.database.repository.review_repo import ReviewRepository
from src.database.models.deal import DealStatus
from src.database.models.ad import AdStatus
from src.services.scheduler_service import SchedulerService

router = Router()

# 1. ТЕЙКЕР ПРИСЫЛАЕТ ЧЕК
@router.message(DealStates.waiting_for_receipt, F.photo)
async def process_taker_receipt(
    message: types.Message, 
    state: FSMContext, 
    bot: Bot, 
    db_session: AsyncSession,
    scheduler: SchedulerService
):
    data = await state.get_data()
    deal_public_id = data.get("current_deal_id")
    if not deal_public_id:
        return await message.answer("❌ Ошибка: Сделка не найдена.")

    photo_id = message.photo[-1].file_id
    deal_repo = DealRepository(db_session)
    
    # Обновляем статус сделки и сохраняем чек покупателя
    await deal_repo.update_deal(
        deal_public_id, 
        status=DealStatus.WAITING_SELLER_CONFIRM, 
        buyer_receipt_id=photo_id
    )
    
    # Останавливаем таймер
    scheduler.remove_deal_timeout_job(deal_public_id)
    
    # Получаем информацию о сделке для уведомления Мейкера
    deal = await deal_repo.get_deal_by_public_id(deal_public_id)
    
    # Пересылаем чек Мейкеру
    await bot.send_photo(
        chat_id=deal.seller_id,
        photo=photo_id,
        caption=f"🔔 Покупатель перевел средства и прикрепил чек. Проверьте поступление!",
        reply_markup=DealKeyboards.confirm_receipt_maker(deal_public_id)
    )
    
    await message.answer("✅ Чек отправлен. Ожидайте подтверждения.")
    await state.clear()

# 2. МЕЙКЕР ПОДТВЕРЖДАЕТ ПОЛУЧЕНИЕ И ПЕРЕВОДИТ СВОЮ ЧАСТЬ
@router.callback_query(F.data.startswith("maker_confirm_"))
async def maker_confirms(
    callback: types.CallbackQuery, 
    state: FSMContext, 
    bot: Bot, 
    db_session: AsyncSession,
    scheduler: SchedulerService
):
    deal_public_id = callback.data.replace("maker_confirm_", "")
    deal_repo = DealRepository(db_session)
    user_repo = UserRepository(db_session)
    
    deal = await deal_repo.get_deal_by_public_id(deal_public_id)
    if not deal:
        return await callback.answer("❌ Сделка не найдена", show_alert=True)

    # Обновляем статус сделки
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await deal_repo.update_deal(
        deal_public_id, 
        status=DealStatus.WAITING_SELLER_PAY,
        expires_at=expires_at
    )
    
    # Ставим новый таймер на 15 минут для Мейкера
    scheduler.add_deal_timeout_job(deal.id, deal_public_id, expires_at)
    
    # Достаем реквизиты Тейкера
    taker_req = await user_repo.get_requisite_by_id(deal.requisite_id)
    
    # Уведомляем Тейкера
    await bot.send_message(
        chat_id=deal.buyer_id,
        text=f"✅ Продавец подтвердил получение. Теперь он переводит средства вам."
    )
    
    # Переводим Мейкера в режим ожидания загрузки чека
    await state.set_state(DealStates.waiting_for_receipt_maker)
    await state.update_data(current_deal_id=deal_public_id)
    
    # Редактируем сообщение Мейкера
    await callback.message.edit_caption(
        caption=(
            f"✅ Вы подтвердили получение средств.\n\n"
            f"Теперь ваша очередь! Переведите средства Тейкеру по реквизитам:\n"
            f"Банк: <b>{taker_req.bank_name}</b>\n"
            f"Реквизиты: <code>{taker_req.details}</code>\n\n"
            f"✅ После перевода, пришлите фото чека в чат.\n\n"
            f"⏳ У вас 15 минут на оплату и отправку чека!"
        ),
        reply_markup=None
    )
    await callback.answer()

# 3. МЕЙКЕР ПРИСЫЛАЕТ ЧЕК
@router.message(DealStates.waiting_for_receipt_maker, F.photo)
async def process_maker_receipt(
    message: types.Message, 
    state: FSMContext, 
    bot: Bot, 
    db_session: AsyncSession,
    scheduler: SchedulerService
):
    data = await state.get_data()
    deal_public_id = data.get("current_deal_id")
    if not deal_public_id:
        return await message.answer("❌ Ошибка: Сделка не найдена.")

    photo_id = message.photo[-1].file_id
    deal_repo = DealRepository(db_session)
    
    # Обновляем БД
    await deal_repo.update_deal(
        deal_public_id, 
        status=DealStatus.WAITING_BUYER_CONFIRM, 
        seller_receipt_id=photo_id
    )
    
    # Останавливаем таймер
    scheduler.remove_deal_timeout_job(deal_public_id)
    
    # Получаем инфо о сделке
    deal = await deal_repo.get_deal_by_public_id(deal_public_id)
    
    # Отправляем фото Тейкеру
    await bot.send_photo(
        chat_id=deal.buyer_id,
        photo=photo_id,
        caption=f"🔔 Продавец перевел средства и прикрепил чек. Проверьте баланс!",
        reply_markup=DealKeyboards.confirm_receipt_taker(deal_public_id)
    )
    
    await message.answer("✅ Чек отправлен покупателю.")
    await state.clear()

# 4. ТЕЙКЕР ПОДТВЕРЖДАЕТ ПОЛУЧЕНИЕ (ЗАВЕРШЕНИЕ)
@router.callback_query(F.data.startswith("taker_confirm_"))
async def taker_confirms(
    callback: types.CallbackQuery, 
    db_session: AsyncSession,
    bot: Bot
):
    deal_public_id = callback.data.replace("taker_confirm_", "")
    deal_repo = DealRepository(db_session)
    ad_repo = AdRepository(db_session)
    user_repo = UserRepository(db_session)

    deal = await deal_repo.get_deal_by_public_id(deal_public_id)
    if not deal:
        return await callback.answer("❌ Сделка не найдена", show_alert=True)

    # Обновляем статус сделки
    try:
        # Завершаем сделку
        await deal_repo.update_deal(deal_public_id, status=DealStatus.COMPLETED)
        # Возвращаем объявление в маркет
        await ad_repo.update_ad_status_by_id(deal.ad_id, AdStatus.ACTIVE)
        # Инкрементируем число сделок для двух пользователей
        await user_repo.increment_deal_count([deal.buyer_id, deal.seller_id])
    except Exception as e:
        return await callback.answer("❌ Ошибка при завершении сделки", show_alert=True)
    
    # Уведомляем Мейкера
    await bot.send_message(
        chat_id=deal.seller_id,
        text=f"🎉 Сделка #{deal_public_id} успешно завершена!"
    )
    
    # Редактируем сообщение Тейкера
    await callback.message.edit_caption(
        caption=f"🎉 Сделка #{deal_public_id} успешно завершена!",
        reply_markup=None
    )
    rating_kb = ReviewKeyboards.get_rating_keyboard(deal.id)
    review_msg = "🙏 <b>Сделка завершена!</b>\nПожалуйста, оцените вашего партнера по сделке:"
    
    # Покупателю
    await callback.message.answer(text=review_msg, reply_markup=rating_kb)
    
    # Продавцу
    await bot.send_message(chat_id=deal.seller_id, text=review_msg, reply_markup=rating_kb)

    # Предложение скрыть объявление продавцу
    ad_info = await ad_repo.get_ad_full_info_by_id(deal.ad_id)
    if ad_info:
        ad, _ = ad_info
        await bot.send_message(
            chat_id=deal.seller_id,
            text=(
                "💡 <b>Совет:</b> Если у вас закончилась ликвидность или вы больше не планируете сегодня торговать, "
                "вы можете скрыть объявление из Маркета прямо сейчас.\n\n"
                "Вернуть его можно в любое время в меню «📢 Мои объявления»."
            ),
            reply_markup=DealKeyboards.get_completion_seller_keyboard(ad.public_id)
        )

    await callback.answer("✅ Сделка завершена!")

@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, db_session: AsyncSession):
    # format: rate_{deal_id}_{score}
    parts = callback.data.split("_")
    deal_id, score = int(parts[1]), int(parts[2])
    
    deal_repo = DealRepository(db_session)
    review_repo = ReviewRepository(db_session)
    
    deal = await deal_repo.get_deal_by_id(deal_id)
    if not deal:
        return await callback.answer("❌ Сделка не найдена", show_alert=True)

    # Определяем, кому ставим оценку (тому, кто НЕ нажимает кнопку сейчас)
    to_user_id = deal.seller_id if callback.from_user.id == deal.buyer_id else deal.buyer_id
    
    success = await review_repo.add_review(
        deal_id=deal.id,
        from_user_id=callback.from_user.id,
        to_user_id=to_user_id,
        score=score
    )
    
    if success:
        await callback.message.edit_text("✅ Спасибо за ваш отзыв! Ваш рейтинг обновлен.")
    else:
        await callback.answer("Вы уже оценивали этого пользователя по данной сделке.", show_alert=True)
        await callback.message.delete()