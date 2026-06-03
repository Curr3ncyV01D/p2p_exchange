from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

class DealKeyboards:
    @staticmethod
    def confirm_receipt_maker(public_id: str) -> InlineKeyboardMarkup:
        """Клавиатура для Мейкера (Шаг 1: Подтверждение получения от Тейкера)"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅ Я получил оплату", 
            callback_data=f"maker_confirm_{public_id}"
        ))
        builder.row(InlineKeyboardButton(
            text="⚖️ Открыть спор", 
            callback_data=f"dispute_{public_id}"
        ))
        return builder.as_markup()

    @staticmethod
    def confirm_receipt_taker(public_id: str) -> InlineKeyboardMarkup:
        """Клавиатура для Тейкера (Шаг 2: Подтверждение получения от Мейкера)"""
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅ Я получил оплату (Завершить сделку)", 
            callback_data=f"taker_confirm_{public_id}"
        ))
        builder.row(InlineKeyboardButton(
            text="⚖️ Открыть спор", 
            callback_data=f"dispute_{public_id}"
        ))
        return builder.as_markup()
