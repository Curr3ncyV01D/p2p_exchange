from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import KeyboardButton

def main_menu_kb():
    builder = ReplyKeyboardBuilder()

    builder.row(KeyboardButton(text="📈 Маркет"))
    builder.row(KeyboardButton(text="💼 Мои сделки"), KeyboardButton(text="📢 Мои объявления"))
    builder.row(KeyboardButton(text="👤 Мой профиль"))

    return builder.as_markup(resize_keyboard=True, input_field_placeholder="Выберите действие...")
