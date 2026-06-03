from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.database.repository.ad_repo import AdRepository
from src.database.models.ad import AdStatus
from src.database.models.user import User
from src.bot.states.ads import AdCreation
from src.bot.keyboards.ads import AdKeyboards
from src.bot.utils.ui_helpers import UIHelper

router = Router()

def get_status_emoji(status: AdStatus) -> str:
    if status == AdStatus.ACTIVE:
        return "🟢"
    if status == AdStatus.HIDDEN:
        return "⚪"
    return "🔘"

@router.message(F.text == "📢 Мои объявления")
async def list_my_ads(message: types.Message, user: User, db_session: AsyncSession):
    ad_repo = AdRepository(db_session)
    ads = await ad_repo.get_user_ads(user.id)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Создать объявление", callback_data="create_new_ad_from_hub"))
    
    for ad in ads:
        emoji = get_status_emoji(ad.status)
        btn_text = f"{emoji} {ad.base_currency.value}/{ad.quote_currency.value} | {ad.rate:,.2f}"
        builder.row(types.InlineKeyboardButton(text=btn_text, callback_data=f"view_my_ad_{ad.public_id}"))
    
    text = "📢 <b>Ваши объявления</b>\n\nЗдесь вы можете управлять своими предложениями в маркете."
    if not ads:
        text += "\n\n<i>У вас пока нет объявлений.</i>"
        
    UIHelper.add_common_buttons(builder)
    
    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "back_to_my_ads")
async def list_my_ads_callback(callback: types.CallbackQuery, user: User, db_session: AsyncSession):
    ad_repo = AdRepository(db_session)
    ads = await ad_repo.get_user_ads(user.id)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Создать объявление", callback_data="create_new_ad_from_hub"))
    
    for ad in ads:
        emoji = get_status_emoji(ad.status)
        btn_text = f"{emoji} {ad.base_currency.value}/{ad.quote_currency.value} | {ad.rate:,.2f}"
        builder.row(types.InlineKeyboardButton(text=btn_text, callback_data=f"view_my_ad_{ad.public_id}"))
    
    text = "📢 <b>Ваши объявления</b>\n\nЗдесь вы можете управлять своими предложениями в маркете."
    if not ads:
        text += "\n\n<i>У вас пока нет объявлений.</i>"
        
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "create_new_ad_from_hub")
async def start_ad_creation_hub(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "<b>Шаг 1 из 5:</b> Выберите валюту, которую вы хотите <b>ПОЛУЧИТЬ</b>:",
        reply_markup=AdKeyboards.get_currency_selection_keyboard()
    )
    await state.set_state(AdCreation.target_currency)
    await callback.answer()

@router.callback_query(F.data.startswith("archive_ad_"))
async def archive_ad(callback: types.CallbackQuery, user: User, db_session: AsyncSession, bot: Bot):
    public_id = callback.data.replace("archive_ad_", "")
    ad_repo = AdRepository(db_session)
    
    ad = await ad_repo.archive_ad(public_id, user.id, is_admin=user.is_admin)
    if ad:
        # Уведомление владельцу, если удалил админ
        if user.is_admin and user.id != ad.user_id:
            try:
                ad_link = UIHelper.get_ad_link(bot_username, ad.public_id)
                await bot.send_message(
                    ad.user_id, 
                    f"⛔ Ваше объявление {ad_link} было удалено администратором.",
                    link_preview_options=types.LinkPreviewOptions(is_disabled=True)
                )
            except Exception: pass
            
        await callback.answer("✅ Объявление удалено (архивировано).")
        if user.is_admin:
            # Если админ удалил через поиск, возвращаем его в главное меню админки или уведомляем
            await callback.message.edit_text("✅ Объявление успешно удалено.")
        else:
            await list_my_ads_callback(callback, user, db_session)
    else:
        await callback.answer("❌ Не удалось удалить объявление.", show_alert=True)

# --- 1. Вспомогательная функция для отрисовки (Render) ---
async def render_my_ad_card(message: types.Message, public_id: str, user_id: int, db_session: AsyncSession, bot_username: str, is_admin: bool = False):
    ad_repo = AdRepository(db_session)
    ad_info = await ad_repo.get_ad_full_info(public_id)
    
    if not ad_info:
        return await message.edit_text("❌ Объявление не найдено.")
    
    ad, owner = ad_info
    
    # Если не админ, проверяем владельца
    if not is_admin and owner.id != user_id:
        return await message.edit_text("❌ Доступ запрещен.")
    
    # Для админа используем back_data="admin_main", для владельца - стандартный возврат
    back_data = "admin_main" if is_admin else "back_to_my_ads"
    text, kb = UIHelper.get_owner_ad_view(ad, bot_username, back_data=back_data)
    
    await message.edit_text(text, reply_markup=kb, link_preview_options=types.LinkPreviewOptions(is_disabled=True))

# --- 2. Хендлер просмотра ---
@router.callback_query(F.data.startswith("view_my_ad_"))
async def view_my_ad(callback: types.CallbackQuery, user: User, db_session: AsyncSession, bot_username: str):
    public_id = callback.data.replace("view_my_ad_", "")
    # Просто вызываем отрисовку с учетом прав админа
    await render_my_ad_card(callback.message, public_id, user.id, db_session, bot_username, is_admin=user.is_admin)
    await callback.answer()

# --- 3. Хендлер переключения (Toggle) ---
@router.callback_query(F.data.startswith("toggle_ad_"))
async def toggle_ad_visibility(callback: types.CallbackQuery, user: User, db_session: AsyncSession, bot_username: str, bot: Bot):
    public_id = callback.data.replace("toggle_ad_", "")
    ad_repo = AdRepository(db_session)
    
    # Меняем статус в базе с учетом прав админа
    ad = await ad_repo.toggle_ad_visibility(public_id, user.id, is_admin=user.is_admin)
    if not ad:
        return await callback.answer("❌ Ошибка при изменении видимости.", show_alert=True)
    
    # Уведомление владельцу, если изменил админ
    if user.is_admin and user.id != ad.user_id:
        status_text = "скрыто" if ad.status == AdStatus.HIDDEN else "активировано"
        try:
            ad_link = UIHelper.get_ad_link(bot_username, ad.public_id)
            await bot.send_message(
                ad.user_id, 
                f"⚠️ Ваше объявление {ad_link} было {status_text} администратором.",
                link_preview_options=types.LinkPreviewOptions(is_disabled=True)
            )
        except Exception: pass
    
    # Сразу перерисовываем это же сообщение новыми данными
    await render_my_ad_card(callback.message, public_id, user.id, db_session, bot_username, is_admin=user.is_admin)
    
    status_msg = "активно" if ad.status == AdStatus.ACTIVE else "скрыто"
    await callback.answer(f"Объявление теперь {status_msg}")