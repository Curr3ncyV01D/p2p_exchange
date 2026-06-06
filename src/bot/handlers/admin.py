from sqlalchemy import select
from sqlalchemy.orm import joinedload
from src.database.repository.verification_repo import VerificationRepository
from src.database.models.verification import VerificationRequest, VerificationStatus
from src.core.config import config
from aiogram import Router, F, types, Bot

from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot.keyboards.profile import ProfileKeyboards
from src.bot.states.verification import VerificationStates
from src.database.repository.dispute_repo import DisputeRepository
from src.bot.states.admin import AdminStates
from src.bot.utils.ui_helpers import UIHelper
from src.database.repository.user_repo import UserRepository
from src.database.repository.ad_repo import AdRepository
from src.database.models.user import User
from src.services.admin_service import AdminService

router = Router()

# Вспомогательная функция для проверки прав (можно вынести в фильтры)
async def check_admin(event: types.Message | types.CallbackQuery, user: User):
    if not user.is_admin:
        if isinstance(event, types.CallbackQuery):
            await event.answer("⛔ Доступ запрещен", show_alert=True)
        return False
    return True

@router.callback_query(F.data == "admin_main")
async def show_admin_main(callback: types.CallbackQuery, user: User):
    if not await check_admin(callback, user): return
    
    await callback.message.edit_text(
        "🛠 <b>Панель администратора</b>\n\nВыберите раздел для управления:",
        reply_markup=ProfileKeyboards.get_admin_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "adm_search")
async def start_user_search(callback: types.CallbackQuery, state: FSMContext, user: User):
    if not await check_admin(callback, user): return
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\nВведите Telegram ID или точный анонимный никнейм:"
    )
    await state.set_state(AdminStates.waiting_for_search_query)
    await callback.answer()

@router.message(AdminStates.waiting_for_search_query)
async def process_user_search(message: types.Message, state: FSMContext, db_session: AsyncSession, user: User):
    if not await check_admin(message, user): return
    
    repo = UserRepository(db_session)
    service = AdminService(db_session, repo)
    
    target_user = await service.search_user(message.text)
    
    if not target_user:
        return await message.answer(
            "❌ Пользователь не найден. Проверьте правильность ID или ника.\n\nПопробуйте еще раз или нажмите /start для отмены."
        )

    await state.clear()
    text = UIHelper.format_admin_user_view(target_user)
    await message.answer(text, reply_markup=ProfileKeyboards.get_admin_user_keyboard(target_user))

@router.callback_query(F.data.startswith("adm_v_"))
async def toggle_verification(callback: types.CallbackQuery, db_session: AsyncSession, user: User):
    """Хендлер переключения галочки ✅"""
    if not await check_admin(callback, user): return
    
    target_id = int(callback.data.split("_")[2])
    repo = UserRepository(db_session)
    service = AdminService(db_session, repo)
    
    target_user = await service.toggle_verify(target_id)
    
    if target_user:
        # Уведомляем пользователя об изменении статуса (опционально)
        try:
            msg = "🌟 Ваш профиль получил статус верифицированного!" if target_user.is_verified else "ℹ️ Статус верификации вашего профиля снят."
            await callback.bot.send_message(target_id, msg)
        except Exception: pass

        # Обновляем карточку в админке
        text = UIHelper.format_admin_user_view(target_user)
        await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_admin_user_keyboard(target_user))
        await callback.answer("Статус обновлен")

@router.callback_query(F.data.startswith("adm_b_"))
async def toggle_ban(callback: types.CallbackQuery, db_session: AsyncSession, user: User):
    """Хендлер переключения бана 🔴"""
    if not await check_admin(callback, user): return
    
    target_id = int(callback.data.split("_")[2])
    repo = UserRepository(db_session)
    service = AdminService(db_session, repo)
    
    target_user = await service.toggle_banned(target_id)
    
    if target_user:
        text = UIHelper.format_admin_user_view(target_user)
        await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_admin_user_keyboard(target_user))
        await callback.answer("Статус блокировки изменен")

@router.callback_query(F.data == "adm_search_ad")
async def start_ad_search(callback: types.CallbackQuery, state: FSMContext, user: User):
    if not await check_admin(callback, user): return
    
    await callback.message.edit_text(
        "📄 <b>Модерация объявления</b>\n\nВведите #ID объявления для модерации:"
    )
    await state.set_state(AdminStates.waiting_for_ad_query)
    await callback.answer()

@router.message(AdminStates.waiting_for_ad_query)
async def process_ad_search(message: types.Message, state: FSMContext, db_session: AsyncSession, user: User, bot_username: str):
    if not await check_admin(message, user): return
    
    ad_id = message.text.replace("#", "").strip()
    ad_repo = AdRepository(db_session)
    
    ad_info = await ad_repo.get_ad_full_info(ad_id)
    
    if not ad_info:
        return await message.answer(
            "❌ Объявление не найдено. Проверьте правильность ID.\n\nПопробуйте еще раз или нажмите /start для отмены."
        )

    await state.clear()
    ad, owner = ad_info
    
    # Используем UIHelper для отображения карточки управления админу
    text, kb = UIHelper.get_owner_ad_view(ad, bot_username, back_data="admin_main")
    
    await message.answer(
        text, 
        reply_markup=kb,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )

# --- Управление верификацией ---

@router.callback_query(F.data == "adm_verif_list")
async def show_verif_list(callback: types.CallbackQuery, db_session: AsyncSession, user: User):
    if not await check_admin(callback, user): return
    
    # Получаем PENDING и ACTIVE заявки
    query = (
        select(VerificationRequest)
        .options(joinedload(VerificationRequest.user))
        .where(VerificationRequest.status.in_([VerificationStatus.PENDING, VerificationStatus.ACTIVE]))
        .order_by(VerificationRequest.created_at.asc())
    )
    result = await db_session.execute(query)
    requests = result.scalars().all()
    
    text = "📂 <b>Заявки на верификацию</b>\n\nНиже список активных запросов от пользователей:"
    if not requests:
        text += "\n\n<i>Список пуст.</i>"
        
    await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_admin_verif_list_keyboard(requests))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_verif_view_"))
async def view_verif_request(callback: types.CallbackQuery, db_session: AsyncSession, user: User):
    if not await check_admin(callback, user): return
    
    request_id = int(callback.data.replace("adm_verif_view_", ""))
    query = (
        select(VerificationRequest)
        .options(joinedload(VerificationRequest.user))
        .where(VerificationRequest.id == request_id)
    )
    result = await db_session.execute(query)
    req = result.scalar_one_or_none()
    
    if not req:
        return await callback.answer("❌ Заявка не найдена", show_alert=True)
        
    text = (
        f"📝 <b>Заявка на верификацию #{req.id}</b>\n\n"
        f"👤 Пользователь: <b>{req.user.display_name}</b>\n"
        f"🆔 ID: <code>{req.user.id}</code>\n"
        f"⭐ Рейтинг: {req.user.rating}\n"
        f"💼 Сделок: {req.user.deal_count}\n"
        f"⚠️ Активные штрафы: {req.user.conflict_strikes}\n"
        f"📅 Дата: {req.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 Статус: <b>{req.status.value.upper()}</b>"
    )
    
    await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_admin_verif_card_keyboard(req.id, req.status))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_verif_chat_"))
async def start_verif_chat(callback: types.CallbackQuery, db_session: AsyncSession, user: User, bot: Bot):
    if not await check_admin(callback, user): return
    
    request_id = int(callback.data.replace("adm_verif_chat_", ""))
    v_repo = VerificationRepository(db_session)
    
    query = select(VerificationRequest).options(joinedload(VerificationRequest.user)).where(VerificationRequest.id == request_id)
    result = await db_session.execute(query)
    req = result.scalar_one_or_none()
    
    if not req or req.status != VerificationStatus.PENDING:
        return await callback.answer("❌ Нельзя начать чат (уже в работе или закрыта)", show_alert=True)

    try:
        # 1. Создаем топик
        topic = await bot.create_forum_topic(
            chat_id=config.ADMIN_GROUP_ID,
            name=f"✅ Верификация: {req.user.display_name}"
        )
        
        # 2. Обновляем статус в базе
        await v_repo.update_request(
            request_id, 
            status=VerificationStatus.ACTIVE, 
            group_topic_id=topic.message_thread_id
        )
        
        # 3. Формируем текст дампа
        dump = (
            f"🔔 <b>Новая сессия верификации #{req.id}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👤 Юзер: {req.user.display_name}\n"
            f"🆔 ID: <code>{req.user.id}</code>\n"
            f"💼 Сделок: {req.user.deal_count}\n"
            f"⭐ Рейтинг: {req.user.rating}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Используйте кнопки ниже для вынесения вердикта."
        )

        await bot.send_message(
            chat_id=config.ADMIN_GROUP_ID, 
            text=dump, 
            message_thread_id=topic.message_thread_id,
            reply_markup=ProfileKeyboards.get_admin_verif_topic_decision_keyboard(req.id)
        )
        
        # 4. Уведомляем пользователя
        await bot.send_message(
            chat_id=req.user.id,
            text="👨‍⚖️ <b>Администратор начал чат по вашей верификации.</b>\n\nВы можете писать свои сообщения прямо здесь."
        )
        
        await callback.message.edit_text("✅ Чат создан в админ-группе. Управление доступно прямо в топике.")
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@router.callback_query(F.data.startswith("adm_verif_approve_"))
async def approve_verif(callback: types.CallbackQuery, db_session: AsyncSession, user: User, bot: Bot):
    if not await check_admin(callback, user): return
    
    request_id = int(callback.data.replace("adm_verif_approve_", ""))
    repo = UserRepository(db_session)
    service = AdminService(db_session, repo)
    
    verification, target_user = await service.resolve_verification(request_id, "approve")
    
    if verification:
        # 1. Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=target_user.id,
                text="🎉 <b>Поздравляем! Ваша верификация успешно пройдена.</b>\n\nТеперь вам доступны все функции площадки и VIP-объявления."
            )
        except Exception: pass
        
        # 2. Закрываем топик если есть
        if verification.group_topic_id:
            try:
                await bot.send_message(config.ADMIN_GROUP_ID, "✅ Верификация одобрена. Чат закрывается.", message_thread_id=verification.group_topic_id)
                await bot.close_forum_topic(config.ADMIN_GROUP_ID, verification.group_topic_id)
            except Exception: pass
            
        await callback.message.edit_text("✅ Верификация одобрена. Пользователь уведомлен.")
        await callback.answer("Одобрено")
    else:
        await callback.answer("❌ Ошибка при обработке", show_alert=True)

# --- Proxy-чат Верификации ---

@router.message(VerificationStates.active_verification)
async def verification_user_to_admin_proxy(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot, user: User):
    """Трансляция сообщений от пользователя к администратору в топик"""
    v_repo = VerificationRepository(db_session)
    
    # Находим активную заявку
    request = await v_repo.get_active_request_by_user(user.id)
    
    if not request or not request.group_topic_id:
        await state.clear()
        return await message.answer("❌ Чат верификации не активен или уже закрыт.")

    # 1. Отправляем префикс
    prefix = f"👤 <b>[КАНДИДАТ] {user.display_name}</b>:"
    await bot.send_message(
        chat_id=config.ADMIN_GROUP_ID, 
        text=prefix, 
        message_thread_id=request.group_topic_id
    )
    
    # 2. Копируем само сообщение
    try:
        await bot.copy_message(
            chat_id=config.ADMIN_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=request.group_topic_id
        )
    except Exception as e:
        print(f"Error proxying user to admin: {e}")

@router.message(F.chat.id == config.ADMIN_GROUP_ID, F.is_topic_message)
async def verification_admin_to_user_proxy(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Трансляция сообщений от администратора из топика к пользователю"""
    # Игнорируем сообщения от ботов и команды
    if message.from_user.is_bot or (message.text and message.text.startswith("/")):
        return

    # 1. Проверяем, не является ли этот топик частью спора (Арбитраж)
    dispute_repo = DisputeRepository(db_session)
    dispute = await dispute_repo.get_dispute_by_topic_id(message.message_thread_id)
    if dispute:
        return # Это сообщение для другого хендлера (dispute.py)

    # 2. Ищем заявку на верификацию по topic_id
    v_repo = VerificationRepository(db_session)
    request = await v_repo.get_request_by_topic_id(message.message_thread_id)
    
    if not request or request.status != VerificationStatus.ACTIVE:
        return

    # 3. Отправляем пользователю
    prefix = "👨‍⚖️ <b>[АДМИН]</b>:"
    try:
        await bot.send_message(chat_id=request.user_id, text=prefix)
        await bot.copy_message(
            chat_id=request.user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
    except Exception as e:
        print(f"Error proxying admin to user: {e}")

@router.callback_query(F.data.startswith("adm_verif_decline_"))
async def decline_verif(callback: types.CallbackQuery, db_session: AsyncSession, user: User, bot: Bot):
    if not await check_admin(callback, user): return
    
    request_id = int(callback.data.replace("adm_verif_decline_", ""))
    repo = UserRepository(db_session)
    service = AdminService(db_session, repo)
    
    verification, target_user = await service.resolve_verification(request_id, "decline")
    
    if verification:
        # 1. Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=target_user.id,
                text="❌ <b>К сожалению, вам отказано в верификации.</b>\n\nЕсли у вас есть вопросы, вы можете связаться с поддержкой."
            )
        except Exception: pass
        
        # 2. Закрываем топик если есть
        if verification.group_topic_id:
            try:
                await bot.send_message(config.ADMIN_GROUP_ID, "❌ В верификации отказано. Чат закрывается.", message_thread_id=verification.group_topic_id)
                await bot.close_forum_topic(config.ADMIN_GROUP_ID, verification.group_topic_id)
            except Exception: pass
            
        await callback.message.edit_text("❌ В верификации отказано. Пользователь уведомлен.")
        await callback.answer("Отклонено")
    else:
        await callback.answer("❌ Ошибка при обработке", show_alert=True)