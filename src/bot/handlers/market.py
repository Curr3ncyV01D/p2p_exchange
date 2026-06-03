from aiogram import Router, F, types, Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import suppress

from src.bot.keyboards.market import MarketKeyboards
from src.bot.utils.formatter import format_number
from src.bot.utils.ui_helpers import UIHelper
from src.database.repository.ad_repo import AdRepository
from src.database.models.ad import Currency
from src.core.constants import CURRENCY_NOMINALS

router = Router()

async def show_market_main(event: types.Message | types.CallbackQuery):
    """Шаг 1: Выбор валюты, которую хотим ПОЛУЧИТЬ"""
    text = (
        "📈 <b>P2P Маркет</b>\n\n"
        "Выберите валюту, которую вы хотите <b>ПОЛУЧИТЬ</b>:"
    )
    kb = MarketKeyboards.get_market_main_keyboard()
    
    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=kb)
    else:
        await event.message.edit_text(text, reply_markup=kb)

@router.message(F.text == "📈 Маркет")
async def market_main_message(message: types.Message):
    await show_market_main(message)

@router.callback_query(F.data == "back_to_market")
async def market_back_callback(callback: types.CallbackQuery):
    await show_market_main(callback)
    await callback.answer()

@router.callback_query(F.data.startswith("m_get_"))
async def select_give_currency(callback: types.CallbackQuery):
    """Шаг 2: Выбор валюты, которую ОТДАЕМ взамен"""
    get_curr = callback.data.replace("m_get_", "")
    
    text = f"💎 Получаем: <b>{get_curr}</b>\n\nВыберите, чем вы будете <b>ПЛАТИТЬ</b>:"
    kb = MarketKeyboards.get_give_currency_keyboard(get_curr)
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("m_pair_"))
async def select_bank(callback: types.CallbackQuery, db_session: AsyncSession):
    """Шаг 3: Выбор банка для конкретной пары"""
    # format: m_pair_{GET}_{GIVE}
    _, _, get_curr, give_curr = callback.data.split("_")
    
    repo = AdRepository(db_session)
    # ВАЖНО: Мы ищем объявления, где человек ОТДАЕТ то, что мы хотим ПОЛУЧИТЬ
    # То есть: Ad.base_currency == get_curr AND Ad.quote_currency == give_curr
    banks = await repo.get_active_banks(get_curr, give_curr, callback.from_user.id)
    
    if not banks:
        await callback.answer("В этом направлении пока нет объявлений", show_alert=True)
        return

    text = f"🏦 <b>{get_curr} ⬅️ {give_curr}</b>\n\nВыберите банк для обмена:"
    await callback.message.edit_text(
        text, 
        reply_markup=MarketKeyboards.get_banks_keyboard(banks, get_curr, give_curr)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("m_bank_"))
async def list_ads(callback: types.CallbackQuery, db_session: AsyncSession):
    """Шаг 4: Список объявлений в выбранном банке"""
    # format: m_bank_{GET}_{GIVE}_{BANK}
    parts = callback.data.split("_")
    get_curr, give_curr = parts[2], parts[3]
    bank = "_".join(parts[4:])
    
    repo = AdRepository(db_session)
    ads = await repo.get_market_ads(get_curr, give_curr, bank, callback.from_user.id)
    
    if not ads:
        await callback.answer("Объявления в этом банке обновились", show_alert=True)
        return await show_market_main(callback)

    text = f"📑 <b>{bank}</b> ({get_curr}/{give_curr})\n\nВыберите подходящее предложение:"
    await callback.message.edit_text(
        text, 
        reply_markup=MarketKeyboards.get_ads_keyboard(ads, get_curr, give_curr, bank)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("view_ad_"))
async def view_ad_card(callback: types.CallbackQuery, db_session: AsyncSession, bot_username: str):
    """Шаг 5: Детальная карточка объявления"""
    public_id = callback.data.replace("view_ad_", "")
    repo = AdRepository(db_session)
    result = await repo.get_ad_full_info(public_id)
    
    if not result:
        await callback.answer("Объявление не найдено", show_alert=True)
        return

    ad, owner = result
    
    # Формируем back_data для возврата в список объявлений этого же банка
    # Мы знаем валюты и банк из самого объявления
    # Важно: В Маркете мы ищем объявления, где человек ОТДАЕТ то, что мы хотим ПОЛУЧИТЬ.
    # Поэтому GET = ad.base_currency, GIVE = ad.quote_currency.
    back_data = f"m_bank_{ad.base_currency.value}_{ad.quote_currency.value}_{ad.bank}"
    
    text, kb = UIHelper.get_guest_ad_view(ad, owner, bot_username, back_data=back_data)
    
    await callback.message.edit_text(
        text, 
        reply_markup=kb,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )
    await callback.answer()