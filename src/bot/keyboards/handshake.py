from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

class HandshakeKeyboards:
    @staticmethod
    def get_maker_decision_keyboard(public_id: str, taker_id: int):
        """Клавиатура для владельца объявления (принять/отклонить запрос)"""
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text="✅ Подтвердить", 
                callback_data=f"accept_{public_id}_{taker_id}"
            ),
            types.InlineKeyboardButton(
                text="❌ Отклонить", 
                callback_data=f"reject_{public_id}_{taker_id}"
            )
        )
        return builder.as_markup()
