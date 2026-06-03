import os
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select

from src.core.config import config
from src.database.repository.deal_repo import DealRepository
from src.database.repository.dispute_repo import DisputeRepository
from src.bot.states.dispute import DisputeStates
from src.database.models.deal import DealStatus
from src.database.models.dispute import Dispute
from src.services.scheduler_service import SchedulerService
from src.database.repository.user_repo import UserRepository
from src.services.admin_service import AdminService
from src.bot.keyboards.admin import AdminKeyboards
from src.bot.keyboards.review import ReviewKeyboards

router = Router()
ADMIN_GROUP_ID = config.ADMIN_GROUP_ID

@router.callback_query(F.data.startswith("dispute_"))
async def start_dispute(callback: types.CallbackQuery, state: FSMContext):
    deal_id = callback.data.split("_")[1]
    await state.update_data(dispute_deal_id=deal_id)
    await state.set_state(DisputeStates.waiting_for_reason)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🤝 Спор решен (Закрыть)", callback_data=f"user_resolve_amicable_{deal_id}"))
    
    await callback.message.answer(
        "⚖️ <b>Арбитраж</b>\n\nПожалуйста, опишите причину открытия спора. "
        "Ваше сообщение и чеки будут переданы арбитру.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# src/bot/handlers/dispute.py

@router.message(DisputeStates.waiting_for_reason)
async def process_dispute_reason(
    message: types.Message, 
    state: FSMContext, 
    db_session: AsyncSession, 
    bot: Bot,
    scheduler: SchedulerService
):
    data = await state.get_data()
    deal_public_id = data.get("dispute_deal_id")
    reason = message.text or "Причина не указана"

    deal_repo = DealRepository(db_session)
    dispute_repo = DisputeRepository(db_session)
    
    deal = await deal_repo.get_deal_by_public_id(deal_public_id)
    if not deal:
        await state.clear()
        return await message.answer("❌ Сделка не найдена.")

    # --- ПРОВЕРКА НА СУЩЕСТВУЮЩИЙ СПОР ---
    # Проверяем, нет ли уже открытого спора по этой сделке
    existing_dispute_stmt = select(Dispute).where(Dispute.deal_id == deal.id)
    result = await db_session.execute(existing_dispute_stmt)
    existing_dispute = result.scalar_one_or_none()

    if existing_dispute:
        await state.clear()
        # Если спор уже есть, просто возвращаем пользователя в режим спора
        for uid in [deal.buyer_id, deal.seller_id]:
            user_key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
            await state.storage.set_state(key=user_key, state=DisputeStates.active_dispute)
            await state.storage.update_data(key=user_key, data={"active_dispute_id": existing_dispute.id})
        
        return await message.answer("⚠️ Спор по этой сделке уже был открыт ранее. Вы переведены в чат с арбитром.")
    # -------------------------------------

    # 1. Замораживаем сделку
    await deal_repo.update_deal(deal_public_id, status=DealStatus.DISPUTED)
    scheduler.remove_deal_timeout_job(deal_public_id)

    # 2. Создаем запись (теперь безопасно)
    dispute = await dispute_repo.create_dispute(deal.id, message.from_user.id, reason)

    # 3. Создаем Topic в админ-группе
    try:
        topic = await bot.create_forum_topic(
            chat_id=ADMIN_GROUP_ID,
            name=f"Спор #{deal_public_id}"
        )
        dispute.group_topic_id = topic.message_thread_id 
        await db_session.commit()
    except Exception as e:
        print(f"Error creating topic: {e}")
        return await message.answer("❌ Ошибка при создании темы в админ-чате.")

    # 4. Отправляем "Дамп сделки" и кнопки резолюции
    admin_text = (
        f"🚨 <b>Новый спор #{deal_public_id}</b>\n\n"
        f"Инициатор: {message.from_user.full_name}\n"
        f"Причина: {reason}\n\n"
        f"Сумма: {deal.amount_base} / {deal.amount_quote}\n"
        f"Покупатель ID: <code>{deal.buyer_id}</code>\n"
        f"Продавец ID: <code>{deal.seller_id}</code>"
    )
    await bot.send_message(
        ADMIN_GROUP_ID, 
        admin_text, 
        message_thread_id=topic.message_thread_id,
        reply_markup=AdminKeyboards.get_dispute_resolution_keyboard(dispute.id)
    )
    
    # Пересылаем чеки
    if deal.buyer_receipt_id:
        await bot.send_photo(ADMIN_GROUP_ID, deal.buyer_receipt_id, caption="Чек покупателя", message_thread_id=topic.message_thread_id)
    if deal.seller_receipt_id:
        await bot.send_photo(ADMIN_GROUP_ID, deal.seller_receipt_id, caption="Чек продавца", message_thread_id=topic.message_thread_id)

    # 5. Переводим обоих участников в режим спора
    for uid in [deal.buyer_id, deal.seller_id]:
        user_key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
        await state.storage.set_state(key=user_key, state=DisputeStates.active_dispute)
        await state.storage.update_data(key=user_key, data={"active_dispute_id": dispute.id})
        await bot.send_message(uid, "⚖️ <b>Администратор вызван в чат.</b>\nВсе ваши сообщения будут транслироваться арбитру.")

# СООБЩЕНИЕ ОТ ЮЗЕРА -> АДМИНУ И ВТОРОМУ УЧАСТНИКУ
@router.message(DisputeStates.active_dispute)
async def user_to_admin_proxy(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    dispute_id = data.get("active_dispute_id")
    
    stmt = select(Dispute).options(joinedload(Dispute.deal)).where(Dispute.id == dispute_id)
    result = await db_session.execute(stmt)
    dispute = result.scalar_one_or_none()
    
    if not dispute: return

    is_buyer = message.from_user.id == dispute.deal.buyer_id
    role = "ПОКУПАТЕЛЬ" if is_buyer else "ПРОДАВЕЦ"
    other_user_id = dispute.deal.seller_id if is_buyer else dispute.deal.buyer_id
    
    prefix_text = f"🗣 <b>[{role}]</b>:"
    
    # 1. Трансляция в админ-топик
    await bot.send_message(ADMIN_GROUP_ID, prefix_text, message_thread_id=dispute.group_topic_id)
    await bot.copy_message(
        chat_id=ADMIN_GROUP_ID, 
        from_chat_id=message.chat.id, 
        message_id=message.message_id, 
        message_thread_id=dispute.group_topic_id
    )

    # 2. Трансляция второму участнику
    try:
        await bot.send_message(other_user_id, prefix_text)
        await bot.copy_message(
            chat_id=other_user_id, 
            from_chat_id=message.chat.id, 
            message_id=message.message_id
        )
    except Exception:
        pass

# СООБЩЕНИЕ ОТ АДМИНА -> ЮЗЕРАМ
@router.message(F.chat.id == ADMIN_GROUP_ID, F.is_topic_message)
async def admin_to_user_proxy(message: types.Message, db_session: AsyncSession, bot: Bot):
    # Игнорируем команды админа и сообщения от ботов
    if message.from_user.is_bot or (message.text and message.text.startswith("/")):
        return

    # Находим спор по topic_id
    dispute_repo = DisputeRepository(db_session)
    dispute = await db_session.execute(
        select(Dispute).options(joinedload(Dispute.deal)).where(Dispute.group_topic_id == message.message_thread_id)
    )
    dispute = dispute.scalar_one_or_none()
    
    if not dispute or dispute.status == "closed":
        return

    prefix_text = "👨‍⚖️ <b>[АРБИТР]</b>:"
    
    for uid in [dispute.deal.buyer_id, dispute.deal.seller_id]:
        try:
            await bot.send_message(uid, prefix_text)
            await bot.copy_message(
                chat_id=uid, 
                from_chat_id=message.chat.id, 
                message_id=message.message_id
            )
        except Exception:
            continue

# РЕЗОЛЮЦИЯ СПОРА (АРБИТР)
@router.callback_query(F.data.startswith("res_"))
async def resolve_dispute_callback(callback: types.CallbackQuery, db_session: AsyncSession, bot: Bot, state: FSMContext):
    # format: res_{action}_{dispute_id} или res_amicable_{action}_{dispute_id}
    parts = callback.data.split("_")
    
    if parts[1] == "amicable":
        action = f"amicable_{parts[2]}"
        dispute_id = int(parts[3])
    else:
        action = parts[1]
        dispute_id = int(parts[2])

    user_repo = UserRepository(db_session)
    admin_service = AdminService(db_session, user_repo)

    deal, dispute = await admin_service.resolve_dispute(dispute_id, action)
    
    if not deal:
        return await callback.answer("❌ Ошибка: Спор или сделка не найдены.", show_alert=True)

    # 3. Сбрасываем FSM состояния у ОБОИХ участников
    for uid in [deal.buyer_id, deal.seller_id]:
        user_key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
        await state.storage.set_state(key=user_key, state=None)
        await state.storage.set_data(key=user_key, data={})
        
        # 4. Отправляем уведомление участникам
        result_text = "завершена" if action == "complete" or action == "amicable_complete" else "отменена"
        can_review = deal.buyer_receipt_id and deal.seller_receipt_id
        
        if action.startswith("amicable_"):
            if can_review:
                msg_text = (
                    f"👨‍⚖️ <b>Спор закрыт миром.</b>\n"
                    f"Сделка <b>{result_text}</b>. Вы можете оценить партнера ниже:"
                )
                reply_markup = ReviewKeyboards.get_rating_keyboard(deal.id)
            else:
                msg_text = (
                    f"👨‍⚖️ <b>Спор закрыт миром.</b>\n"
                    f"Сделка <b>{result_text}</b>. Возможность оставить отзыв недоступна, так как обмен не был завершен обеими сторонами."
                )
                reply_markup = None
        else:
            if can_review:
                msg_text = (
                    f"👨‍⚖️ <b>Решение по спору сделки #{deal.public_id}</b>\n\n"
                    f"Арбитр изучил доказательства. Сделка <b>{result_text}</b>. "
                    f"Вы можете оценить партнера ниже:"
                )
                reply_markup = ReviewKeyboards.get_rating_keyboard(deal.id)
            else:
                msg_text = (
                    f"👨‍⚖️ <b>Решение по спору сделки #{deal.public_id}</b>\n\n"
                    f"Арбитр изучил доказательства. Сделка <b>{result_text}</b>. "
                    f"Возможность оставить отзыв недоступна, так как обмен не был завершен обеими сторонами."
                )
                reply_markup = None

        await bot.send_message(
            chat_id=uid,
            text=msg_text,
            reply_markup=reply_markup
        )

    # 5. Отправляем сообщение в топик админов
    await bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"🏁 <b>Спор закрыт решением:</b> {action.upper()}",
        message_thread_id=dispute.group_topic_id
    )

    # 6. Закрываем топик в Telegram
    try:
        await bot.close_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=dispute.group_topic_id)
    except Exception as e:
        print(f"Error closing topic: {e}")

    # 7. Убираем кнопки у сообщения админа
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Спор закрыт")

# МИРНОЕ РЕШЕНИЕ ПОЛЬЗОВАТЕЛЕМ
@router.callback_query(F.data.startswith("user_resolve_amicable_"))
async def user_resolve_dispute(callback: types.CallbackQuery, db_session: AsyncSession, bot: Bot, state: FSMContext):
    deal_public_id = callback.data.split("_")[-1]
    
    deal_repo = DealRepository(db_session)
    deal = await deal_repo.get_deal_by_public_id(deal_public_id)
    if not deal:
        return await callback.answer("❌ Сделка не найдена.", show_alert=True)
    
    # Находим активный спор
    dispute_stmt = select(Dispute).where(Dispute.deal_id == deal.id, Dispute.status == "open")
    result = await db_session.execute(dispute_stmt)
    dispute = result.scalar_one_or_none()
    
    if not dispute:
        return await callback.answer("❌ Активный спор не найден.", show_alert=True)

    # Определяем действие в зависимости от роли (по умолчанию Buyer закрывает как завершенную)
    # Если спор открыл покупатель и он же закрывает -> amicable_complete
    # Если продавец -> amicable_cancel (или наоборот, зависит от логики, но возьмем простейшую: 
    # закрытие инициатором = проблема решена)
    action = "amicable_complete" if callback.from_user.id == deal.buyer_id else "amicable_cancel"
    
    user_repo = UserRepository(db_session)
    admin_service = AdminService(db_session, user_repo)
    
    await admin_service.resolve_dispute(dispute.id, action)

    # Сбрасываем стейты
    can_review = deal.buyer_receipt_id and deal.seller_receipt_id
    for uid in [deal.buyer_id, deal.seller_id]:
        user_key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
        await state.storage.set_state(key=user_key, state=None)
        await state.storage.set_data(key=user_key, data={})
        
        if can_review:
            text = f"🤝 <b>Спор по сделке #{deal.public_id} решен мирным путем.</b>\nДоступ к функциям бота восстановлен. Вы можете оценить партнера ниже:"
            reply_markup = ReviewKeyboards.get_rating_keyboard(deal.id)
        else:
            text = f"🤝 <b>Спор по сделке #{deal.public_id} решен мирным путем.</b>\nДоступ к функциям бота восстановлен. Возможность оставить отзыв недоступна, так как обмен не был завершен обеими сторонами."
            reply_markup = None

        await bot.send_message(
            chat_id=uid,
            text=text,
            reply_markup=reply_markup
        )

    # Уведомляем админов
    await bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"🤝 <b>Спор закрыт пользователем (МИРНО):</b> {action.upper()}",
        message_thread_id=dispute.group_topic_id
    )
    
    try:
        await bot.close_forum_topic(chat_id=ADMIN_GROUP_ID, message_thread_id=dispute.group_topic_id)
    except Exception: pass

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Спор закрыт")

