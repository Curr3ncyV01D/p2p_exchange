from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

class AdminKeyboards:
    @staticmethod
    def get_dispute_resolution_keyboard(dispute_id: int):
        builder = InlineKeyboardBuilder()
        # В пользу покупателя (подтвердить получение за продавца)
        builder.row(InlineKeyboardButton(
            text="✅ Завершить (в пользу Покупателя)", 
            callback_data=f"res_complete_{dispute_id}"
        ))
        # В пользу продавца (отменить сделку)
        builder.row(InlineKeyboardButton(
            text="❌ Отменить (в пользу Продавца)", 
            callback_data=f"res_cancel_{dispute_id}"
        ))
        # Мирное решение (без страйков)
        builder.row(InlineKeyboardButton(
            text="🤝 Мирное решение: Завершить", 
            callback_data=f"res_amicable_complete_{dispute_id}"
        ))
        builder.row(InlineKeyboardButton(
            text="🤝 Мирное решение: Отменить", 
            callback_data=f"res_amicable_cancel_{dispute_id}"
        ))
        return builder.as_markup()