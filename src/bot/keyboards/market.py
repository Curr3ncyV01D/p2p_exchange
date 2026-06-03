from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.bot.utils.ui_helpers import UIHelper
from src.database.models.ad import Currency
from src.core.constants import CURRENCY_NOMINALS

class MarketKeyboards:
    @staticmethod
    def get_market_main_keyboard():
        """Главное меню маркета: выбор валюты, которую человек хочет ПОЛУЧИТЬ"""
        builder = InlineKeyboardBuilder()
        # Показываем все доступные валюты как цели получения
        for curr in Currency:
            builder.row(types.InlineKeyboardButton(
                text=f"💎 Приобрести {curr.value}", 
                callback_data=f"m_get_{curr.value}"
            ))
        UIHelper.add_common_buttons(builder)
        return builder.as_markup()

    @staticmethod
    def get_give_currency_keyboard(get_curr: str):
        """Второй шаг: чем человек будет ПЛАТИТЬ за выбранную валюту"""
        builder = InlineKeyboardBuilder()
        for curr in Currency:
            if curr.value == get_curr:
                continue
            builder.row(types.InlineKeyboardButton(
                text=f"💳 Купить за {curr.value}", 
                callback_data=f"m_pair_{get_curr}_{curr.value}"
            ))
        UIHelper.add_common_buttons(builder, back_data="back_to_market")
        return builder.as_markup()

    @staticmethod
    def get_banks_keyboard(banks: list, get_curr: str, give_curr: str):
        builder = InlineKeyboardBuilder()
        for bank_name, count in banks:
            builder.row(types.InlineKeyboardButton(
                text=f"{bank_name} ({count})", 
                callback_data=f"m_bank_{get_curr}_{give_curr}_{bank_name}"
            ))
        UIHelper.add_common_buttons(builder, back_data=f"m_get_{get_curr}")
        return builder.as_markup()

    @staticmethod
    def get_ads_keyboard(ads: list, get_curr: str, give_curr: str, bank: str):
        builder = InlineKeyboardBuilder()
        for ad, user in ads:
            # Превью: "Ник | Курс | Лимиты"
            nominal = CURRENCY_NOMINALS.get(ad.base_currency.value, 1)
            nominal_text = f" (за {nominal/1000:,.0f}к)" if nominal >= 1000 else ""
            btn_text = f"{user.display_name} | {ad.rate}{nominal_text} | {ad.min_limit:,.0f}-{ad.max_limit:,.0f}"
            builder.row(types.InlineKeyboardButton(
                text=btn_text, 
                callback_data=f"view_ad_{ad.public_id}"
            ))
        UIHelper.add_common_buttons(builder, back_data=f"m_pair_{get_curr}_{give_curr}")
        return builder.as_markup()
    
    @staticmethod
    def get_ad_view_keyboard(public_id: str, get_curr: str, give_curr: str, bank: str):
        """Клавиатура детального просмотра объявления"""
        builder = InlineKeyboardBuilder()
        
        # Кнопка инициации сделки
        builder.row(types.InlineKeyboardButton(
            text="🤝 Начать сделку", 
            callback_data=f"start_deal_{public_id}"
        ))
        
        # Кнопка Назад должна вести точно в тот список объявлений, из которого пришел юзер.
        # Формат: m_bank_{GET}_{GIVE}_{BANK}
        back_callback = f"m_bank_{get_curr}_{give_curr}_{bank}"
        
        UIHelper.add_common_buttons(builder, back_data=back_callback)
        return builder.as_markup()