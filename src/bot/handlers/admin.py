from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.profile import ProfileKeyboards
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