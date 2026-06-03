from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states.ads import AdCreation
from src.bot.keyboards.ads import AdKeyboards
from src.bot.utils.ui_helpers import UIHelper
from src.bot.utils.formatter import format_number
from src.core.constants import CURRENCY_NOMINALS
from src.database.models.ad import Currency
from src.database.repository.ad_repo import AdRepository
from src.database.repository.user_repo import UserRepository
from src.services.hashing import generate_public_id
from decimal import Decimal

router = Router()

@router.message(F.text == "➕ Создать объявление")
async def start_ad_creation(message: types.Message, state: FSMContext):
    await message.answer(
        "<b>Шаг 1 из 5:</b> Выберите валюту, которую вы хотите <b>ПОЛУЧИТЬ</b>:",
        reply_markup=AdKeyboards.get_currency_selection_keyboard()
    )
    await state.set_state(AdCreation.target_currency)

@router.callback_query(AdCreation.target_currency, F.data.startswith("curr_"))
async def process_target_currency(callback: types.CallbackQuery, state: FSMContext):
    target_curr = callback.data.split("_")[1]
    await state.update_data(target_currency=target_curr)
    
    await callback.message.edit_text(
        f"Вы хотите получить: <b>{target_curr}</b>\n\n"
        "<b>Шаг 2 из 5:</b> Выберите валюту, которую вы <b>ОТДАЕТЕ</b> взамен:",
        reply_markup=AdKeyboards.get_currency_selection_keyboard(exclude=target_curr)
    )
    await state.set_state(AdCreation.base_currency)

@router.callback_query(AdCreation.base_currency, F.data.startswith("curr_"))
async def process_base_currency(callback: types.CallbackQuery, state: FSMContext):
    base_curr = callback.data.split("_")[1]

    await state.update_data(base_currency=base_curr)
    data = await state.get_data()
    target_curr = data.get("target_currency")
    
    # Номинал валюты, которую юзер ПОЛУЧАЕТ
    nominal = CURRENCY_NOMINALS.get(target_curr, 1)

    await callback.message.edit_text(
        f"Направление: <b>{base_curr} ➡️ {target_curr}</b>\n\n"
        f"<b>Шаг 3 из 5: Курс</b>\n"
        f"Введите стоимость {nominal} {target_curr} в {base_curr}.\n"
        f"<i>Пример: 72.5 (за {nominal} {target_curr} вы отдадите 72.5 {base_curr})</i>"
    )
    await state.set_state(AdCreation.rate)

@router.message(AdCreation.rate)
async def process_rate(message: types.Message, state: FSMContext):
    try:
        rate = Decimal(message.text.replace(" ", "").replace(',', '.'))
        if rate <= 0: raise ValueError
    except:
        return await message.answer("❌ Введите положительное число.")

    await state.update_data(rate=str(rate))
    await message.answer("<b>Шаг 4.1 из 5: Лимиты</b>\nВведите МИНИМАЛЬНУЮ сумму одной сделки:")
    await state.set_state(AdCreation.min_limit)

@router.message(AdCreation.min_limit)
async def process_min_limit(message: types.Message, state: FSMContext):
    try:
        min_val = Decimal(message.text.replace(" ", "").replace(',', '.'))
        if min_val <= 0: raise ValueError
    except:
        return await message.answer("❌ Введите положительное число.")

    await state.update_data(min_limit=str(min_val))
    await message.answer("<b>Шаг 4.2 из 5: Лимиты</b>\nВведите ОБЩИЙ ОБЪЕМ (максимальную сумму) обмена:")
    await state.set_state(AdCreation.max_limit)

@router.message(AdCreation.max_limit)
async def process_max_limit(message: types.Message, state: FSMContext, db_session: AsyncSession):
    try:
        max_val = Decimal(message.text.replace(" ", "").replace(',', '.'))
        data = await state.get_data()
        if max_val <= Decimal(data['min_limit']): raise ValueError
    except:
        return await message.answer("❌ Максимальный лимит должен быть больше минимального.")

    await state.update_data(max_limit=str(max_val))
    
    user_repo = UserRepository(db_session)
    requisites = await user_repo.get_user_requisites(message.from_user.id)
    
    if not requisites:
        await message.answer("❌ У вас нет реквизитов. Добавьте их в профиле.")
        return await state.clear()

    await message.answer(
        "<b>Шаг 5 из 5: Реквизиты</b>\nВыберите карту для получения/оплаты:",
        reply_markup=AdKeyboards.get_requisite_selection_keyboard(requisites)
    )
    await state.set_state(AdCreation.requisite)

@router.callback_query(AdCreation.requisite, F.data.startswith("req_"))
async def process_requisite(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    req_id = int(callback.data.split("_")[1])
    user_repo = UserRepository(db_session)
    requisite = await user_repo.get_requisite_by_id(req_id)
    
    await state.update_data(requisite_id=req_id, bank=requisite.bank_name)
    data = await state.get_data()
    
    # ФОРМИРУЕМ ПРЕВЬЮ ДЛЯ ЛИМИТОВ
    base = data['base_currency']
    target = data['target_currency']
    rate = data['rate']
    nominal = CURRENCY_NOMINALS.get(target, 1)
    
    summary = (
        f"📋 <b>Проверьте данные объявление:</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔄 <b>Направление:</b> {base} ➡️ {target}\n"
        f"💰 <b>Курс:</b> {format_number(rate)} {base} за {nominal} {target}\n"
        f"🏦 <b>Банк:</b> {data['bank']}\n"
        f"📏 <b>Лимиты:</b> {format_number(data['min_limit'])} - {format_number(data['max_limit'])} {base}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>Объявление будет висеть в маркете, пока вы его не скроете.</i>"
    )
    
    await callback.message.edit_text(summary, reply_markup=AdKeyboards.get_confirm_keyboard())
    await state.set_state(AdCreation.confirm)

@router.callback_query(AdCreation.confirm, F.data == "confirm_ad")
async def finalize_ad(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession, bot_username: str):
    data = await state.get_data()
    repo = AdRepository(db_session)
    
    public_id = generate_public_id()
    await repo.create_ad(callback.from_user.id, public_id, data['requisite_id'], data)
    
    ad_link = UIHelper.get_ad_link(bot_username, public_id)
    
    await callback.message.edit_text(
        f"✅ <b>Объявление опубликовано!</b>\nПубличный ID: {ad_link}",
        reply_markup=AdKeyboards.get_success_keyboard(),
        link_preview_options=types.LinkPreviewOptions(is_disabled=True)
    )
    await state.clear()
    await callback.answer()