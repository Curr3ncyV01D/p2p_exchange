from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from src.bot.utils.ui_helpers import UIHelper
from src.database.models.user import User

class ProfileKeyboards:
    @staticmethod
    def get_profile_keyboard(is_admin: bool = False):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💳 Мои реквизиты", callback_data="my_requisites"))
        
        # Если юзер админ — добавляем кнопку входа в панель
        if is_admin:
            builder.row(InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_main"))
            
        UIHelper.add_common_buttons(builder)
        return builder.as_markup()

    @staticmethod
    def get_admin_main_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm_search"))
        builder.row(InlineKeyboardButton(text="📄 Найти объявление", callback_data="adm_search_ad"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_to_profile"))
        return builder.as_markup()

    @staticmethod
    def get_admin_user_keyboard(target_user: User):
        builder = InlineKeyboardBuilder()
        
        v_text = "❌ Снять верификацию" if target_user.is_verified else "✅ Верифицировать"
        b_text = "🟢 Разбанить" if target_user.is_banned else "🔴 Забанить"
        
        builder.row(InlineKeyboardButton(text=v_text, callback_data=f"adm_v_{target_user.id}"))
        builder.row(InlineKeyboardButton(text=b_text, callback_data=f"adm_b_{target_user.id}"))
        builder.row(InlineKeyboardButton(text="🔙 Назад к поиску", callback_data="adm_search"))
        
        return builder.as_markup()

    @staticmethod
    def get_requisites_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="➕ Добавить реквизиты", callback_data="add_requisite"))
        UIHelper.add_common_buttons(builder, back_data="back_to_profile")
        return builder.as_markup()
