from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from src.bot.utils.ui_helpers import UIHelper

class ReviewKeyboards:
    @staticmethod
    def get_rating_keyboard(deal_id: int):
        builder = InlineKeyboardBuilder()

        for i in range(5, 0, -1):
            builder.add(InlineKeyboardButton(
                text=f"{'⭐' * i}", 
                callback_data=f"rate_{deal_id}_{i}"
            ))
        builder.adjust(1, 2, 2) # Каждая звезда на новой строке или .adjust(5) в ряд
        UIHelper.add_common_buttons(builder)
        return builder.as_markup()
