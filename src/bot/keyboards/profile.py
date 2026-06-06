from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from src.bot.utils.ui_helpers import UIHelper
from src.database.models.user import User
from src.database.models.verification import VerificationRequest, VerificationStatus

class ProfileKeyboards:
    @staticmethod
    def get_profile_keyboard(user: User, verification: VerificationRequest | None = None):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💳 Мои реквизиты", callback_data="my_requisites"))
        
        if not user.is_verified:
            if not verification:
                builder.row(InlineKeyboardButton(text="🌟 Пройти верификацию", callback_data="start_verification"))
            else:
                builder.row(InlineKeyboardButton(text="💬 Чат верификации", callback_data="open_verification_chat"))

        if user.is_admin:
            builder.row(InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_main"))
            
        UIHelper.add_common_buttons(builder)
        return builder.as_markup()

    @staticmethod
    def get_verification_confirm_keyboard():
        """Клавиатура подтверждения подачи заявки на верификацию"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✅ Подать заявку", callback_data="submit_verification"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile"))
        return builder.as_markup()

    @staticmethod
    def get_admin_main_keyboard():
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm_search"))
        builder.row(InlineKeyboardButton(text="📄 Найти объявление", callback_data="adm_search_ad"))
        builder.row(InlineKeyboardButton(text="📂 Заявки на верификацию", callback_data="adm_verif_list"))
        builder.row(InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_to_profile"))
        return builder.as_markup()

    @staticmethod
    def get_admin_verif_list_keyboard(requests: list[VerificationRequest]):
        """Список заявок на верификацию"""
        builder = InlineKeyboardBuilder()
        for req in requests:
            builder.row(InlineKeyboardButton(
                text=f"📝 {req.user.display_name}", 
                callback_data=f"adm_verif_view_{req.id}"
            ))
        builder.row(InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_main"))
        return builder.as_markup()

    @staticmethod
    def get_admin_verif_card_keyboard(request_id: int, status: VerificationStatus):
        """Карточка управления заявкой на верификацию"""
        builder = InlineKeyboardBuilder()
        
        if status == VerificationStatus.PENDING:
            builder.row(InlineKeyboardButton(text="💬 Начать диалог", callback_data=f"adm_verif_chat_{request_id}"))
        
        builder.row(
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm_verif_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_verif_decline_{request_id}")
        )
        builder.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="adm_verif_list"))
        return builder.as_markup()

    @staticmethod
    def get_admin_verif_topic_decision_keyboard(request_id: int):
        """Кнопки решения прямо внутри топика верификации"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm_verif_approve_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_verif_decline_{request_id}")
        )
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
