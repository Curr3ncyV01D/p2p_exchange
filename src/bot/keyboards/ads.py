from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.bot.utils.ui_helpers import UIHelper
from src.database.models.ad import Currency

class AdKeyboards:
    @staticmethod
    def get_currency_selection_keyboard(exclude: str = None):
        """
        Универсальная клавиатура для выбора валют.
        Используется и для 'Получаю', и для 'Отдаю'.
        """
        builder = InlineKeyboardBuilder()

        for curr in Currency:
            if exclude and curr.value == exclude:
                continue
            
            builder.row(types.InlineKeyboardButton(
                text=f"💰 {curr.value}", 
                callback_data=f"curr_{curr.value}"
            ))
            
        UIHelper.add_common_buttons(builder, close=True)
        return builder.as_markup()

    @staticmethod
    def get_requisite_selection_keyboard(requisites):
        """Клавиатура выбора карты для привязки к объявлению"""
        builder = InlineKeyboardBuilder()
        
        for req in requisites:
            # Форматируем текст: "Сбербанк *1234"
            last_four = str(req.details)[-4:] if len(str(req.details)) >= 4 else req.details
            btn_text = f"💳 {req.bank_name} *{last_four}"
            
            builder.row(types.InlineKeyboardButton(
                text=btn_text, 
                callback_data=f"req_{req.id}"
            ))
            
        UIHelper.add_common_buttons(builder, close=True)
        return builder.as_markup()

    @staticmethod
    def get_confirm_keyboard():
        """Финальное подтверждение создания"""
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="✅ Опубликовать", callback_data="confirm_ad"),
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="common_close")
        )
        return builder.as_markup()

    @staticmethod
    def get_success_keyboard():
        """Сообщение об успехе"""
        builder = InlineKeyboardBuilder()
        UIHelper.add_common_buttons(builder)
        return builder.as_markup()