from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from src.bot.states.deals import DealStates
from src.bot.keyboards.handshake import HandshakeKeyboards
from src.bot.keyboards.ads import AdKeyboards
from src.bot.utils.formatter import format_number
from src.bot.utils.ui_helpers import UIHelper

from src.database.repository.ad_repo import AdRepository
from src.database.repository.user_repo import UserRepository
from src.database.repository.deal_repo import DealRepository
from src.database.models.ad import AdStatus
from src.services.hashing import generate_public_id
from src.services.scheduler_service import SchedulerService
from src.core.constants import CURRENCY_NOMINALS

router = Router()

# 1. ТЕЙКЕР ЖМЕТ "НАЧАТЬ СДЕЛКУ" В МАРКЕТЕ
@router.callback_query(F.data.startswith("start_deal_"))
async def request_deal(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession):
    deal_public_id = callback.data.replace("start_deal_", "")
    ad_repo = AdRepository(db_session)
    deal_repo = DealRepository(db_session)

    # Пока НЕ резервируем объявление, просто проверяем, что оно доступно
    ad_info = await ad_repo.get_ad_full_info(deal_public_id)
    if not ad_info:
        return await callback.answer("❌ Объявление не найдено!", show_alert=True)
        
    ad, owner = ad_info
    
    if ad.status != AdStatus.ACTIVE:
        return await callback.answer("❌ Объявление уже неактуально или скрыто!", show_alert=True)
    
    active_deals = await deal_repo.get_active_deals_by_user(callback.from_user.id)
    if len(active_deals) >= 1:
        return await callback.answer("❌ У вас уже есть активная сделка. Завершите её перед началом новой.", show_alert=True)
        
    if owner.id == callback.from_user.id:
        return await callback.answer("❌ Вы не можете открыть сделку с самим собой!", show_alert=True)

    # Сохраняем ID объявления в FSM Тейкера
    await state.update_data(deal_ad_id=deal_public_id)
    
    await callback.message.edit_text(
        f"💰 <b>Сделка по {ad.base_currency.value}</b>\n\n"
        f"Лимиты: {format_number(ad.min_limit)} - {format_number(ad.max_limit)} {ad.base_currency.value}\n"
        f"Введите сумму в <b>{ad.base_currency.value}</b>, которую хотите обменять:"
    )
    await state.set_state(DealStates.waiting_for_amount)
    await callback.answer()

# 2. ТЕЙКЕР ВВОДИТ СУММУ
@router.message(DealStates.waiting_for_amount)
async def process_deal_amount(message: types.Message, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    deal_public_id = data.get("deal_ad_id")
    
    ad_repo = AdRepository(db_session)
    ad_info = await ad_repo.get_ad_full_info(deal_public_id)
    if not ad_info or ad_info[0].status != AdStatus.ACTIVE:
        await state.clear()
        return await message.answer("❌ Объявление уже неактуально.")
        
    ad, _ = ad_info
    
    # Валидация суммы и лимитов
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
        if amount < ad.min_limit or amount > ad.max_limit:
            raise ValueError
    except ValueError:
        return await message.answer(f"❌ Введите число от {format_number(ad.min_limit)} до {format_number(ad.max_limit)}.")
        
    await state.update_data(deal_amount=str(amount))
    
    # Проверяем, есть ли у Тейкера реквизиты
    user_repo = UserRepository(db_session)
    reqs = await user_repo.get_user_requisites(message.from_user.id)
    
    if not reqs:
        await state.clear()
        return await message.answer("❌ У вас нет реквизитов! Пожалуйста, добавьте карту в разделе «Мой профиль».")
        
    await message.answer(
        f"💳 Вы обмениваете <b>{format_number(amount)} {ad.base_currency.value}</b>.\n\n"
        f"Выберите ВАШУ карту, которая будет участвовать в сделке:",
        reply_markup=AdKeyboards.get_requisite_selection_keyboard(reqs)
    )
    await state.set_state(DealStates.waiting_for_requisite)

# 3. ТЕЙКЕР ВЫБИРАЕТ СВОЮ КАРТУ -> ЗАПРОС УЛЕТАЕТ МЕЙКЕРУ
@router.callback_query(DealStates.waiting_for_requisite, F.data.startswith("req_"))
async def process_deal_requisite(callback: types.CallbackQuery, state: FSMContext, bot: Bot, db_session: AsyncSession, bot_username: str):
    req_id = int(callback.data.split("_")[1])
    await state.update_data(taker_req_id=req_id)
    
    data = await state.get_data()
    deal_public_id = data.get("deal_ad_id")
    amount = Decimal(data.get("deal_amount"))
    
    ad_repo = AdRepository(db_session)
    
    # Теперь АТОМАРНО резервируем объявление (защита от гонки)
    ad = await ad_repo.try_reserve_ad(deal_public_id)
    if not ad:
        await state.clear()
        return await callback.answer("❌ Продавец уже начал сделку с другим покупателем! Подождите немного", show_alert=True)
        
    ad_info = await ad_repo.get_ad_full_info(deal_public_id)
    _, owner = ad_info
    taker_id = callback.from_user.id

    try:
        ad_link = UIHelper.get_ad_link(bot_username, deal_public_id)
        
        text_for_owner = (
            f"🔔 <b>Новый отклик на объявление {ad_link}!</b>\n\n"
            f"Пользователь готов обменять <b>{format_number(amount)} {ad.base_currency.value}</b>.\n"
            f"Подтверждаете начало сделки?"
        )
        await bot.send_message(
            chat_id=owner.id,
            text=text_for_owner,
            reply_markup=HandshakeKeyboards.get_maker_decision_keyboard(deal_public_id, taker_id),
            link_preview_options=types.LinkPreviewOptions(is_disabled=True)
        )
        
        await callback.message.edit_text("⏳ <b>Запрос отправлен продавцу.</b>\nОжидайте подтверждения...", reply_markup=None)
    except Exception:
        await ad_repo.update_ad_status_by_id(deal_public_id, AdStatus.ACTIVE)
        await callback.answer("❌ Не удалось связаться с продавцом.", show_alert=True)

    # Мы НЕ очищаем state Тейкера! Данные нужны Мейкеру.
    await callback.answer()

# 4. МЕЙКЕР ПОДТВЕРЖДАЕТ СДЕЛКУ
@router.callback_query(F.data.startswith("accept_"))
async def handle_accept(
    callback: types.CallbackQuery, 
    bot: Bot, 
    state: FSMContext,
    db_session: AsyncSession,
    scheduler: SchedulerService
):
    parts = callback.data.split("_")
    deal_public_id, taker_id = parts[1], int(parts[2])

    # Читаем FSM Тейкера, чтобы узнать введенную сумму и его карту
    taker_key = StorageKey(bot_id=bot.id, chat_id=taker_id, user_id=taker_id)
    taker_data = await state.storage.get_data(key=taker_key)
    
    amount_base_str = taker_data.get("deal_amount")
    taker_req_id = taker_data.get("taker_req_id")

    # Если почему-то данных нет (таймаут Redis), отменяем всё безопасно
    if not amount_base_str or not taker_req_id:
        ad_repo = AdRepository(db_session)
        await ad_repo.update_ad_status_by_id(deal_public_id, AdStatus.ACTIVE)
        return await callback.message.edit_text("❌ Ошибка данных сессии. Объявление возвращено в маркет.")

    amount_base = Decimal(amount_base_str)

    ad_repo = AdRepository(db_session)
    user_repo = UserRepository(db_session)
    deal_repo = DealRepository(db_session)

    ad_info = await ad_repo.get_ad_full_info(deal_public_id)
    ad, owner = ad_info
    
    # Получаем реквизиты ПРОДАВЦА (Мейкера) из объявления
    maker_req = await user_repo.get_requisite_by_id(ad.requisite_id)

    # ЛОГИКА MVP: В 1-м шаге Тейкер платит Мейкеру.
    buyer_id = taker_id
    seller_id = owner.id

    # Считаем сумму, которую нужно оплатить
    nominal = CURRENCY_NOMINALS.get(ad.base_currency.value, 1)
    amount_quote = (amount_base / Decimal(str(nominal))) * Decimal(str(ad.rate))
    
    deal_public_id = generate_public_id()

    # СОЗДАЕМ СДЕЛКУ (В DealRepository теперь сохраняем taker_req_id как requisite_id)
    deal = await deal_repo.create_deal(
        ad_id=ad.id,
        public_id=deal_public_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        requisite_id=taker_req_id,
        amount_base=float(amount_base),
        amount_quote=float(amount_quote)
    )

    scheduler.add_deal_timeout_job(deal.id, deal.public_id, deal.expires_at)

    text_common = (
        f"✅ <b>Сделка #{deal.public_id} начата!</b>\n"
        f"Сумма: {format_number(amount_base)} {ad.base_currency.value} 🔄 {format_number(amount_quote)} {ad.quote_currency.value}\n\n"
    )

    # ПИШЕМ ПОКУПАТЕЛЮ (Тейкеру) -> Даем ему реквизиты Мейкера для перевода
    await bot.send_message(
        chat_id=buyer_id,
        text=text_common + f"💳 Переведите <b>{format_number(amount_quote)} {ad.quote_currency.value}</b> на реквизиты:\n"
                           f"Банк: {maker_req.bank_name}\n"
                           f"Данные: <code>{maker_req.details}</code>\n\n"
                           f"✅ После перевода, отправьте чек в этот чат.\n"
                           f"⏳ У вас 15 минут на оплату и отправку чека!"
    )

    # Очищаем кэш Тейкера (переводим его в статус загрузки чека)
    await state.storage.set_state(key=taker_key, state=DealStates.waiting_for_receipt)
    await state.storage.update_data(key=taker_key, data={"current_deal_id": deal.public_id})

    # ПИШЕМ ПРОДАВЦУ (Мейкеру)
    await callback.message.edit_text(
        text_common + "⏳ Ожидайте оплату от покупателя. У него есть 15 минут.",
        reply_markup=None
    )
    await callback.answer()

# 5. МЕЙКЕР ОТКЛОНЯЕТ СДЕЛКУ
@router.callback_query(F.data.startswith("reject_"))
async def handle_reject(callback: types.CallbackQuery, bot: Bot, state: FSMContext, db_session: AsyncSession):
    parts = callback.data.split("_")
    deal_public_id, taker_id = parts[1], int(parts[2])

    ad_repo = AdRepository(db_session)
    await ad_repo.update_ad_status_by_id(deal_public_id, AdStatus.ACTIVE)

    # Очищаем кэш тейкера
    taker_key = StorageKey(bot_id=bot.id, chat_id=taker_id, user_id=taker_id)
    await state.storage.set_data(key=taker_key, data={})

    try:
        await bot.send_message(chat_id=taker_id, text=f"❌ Владелец отклонил запрос по объявлению #{deal_public_id}")
    except Exception: pass

    await callback.message.edit_text("❌ Запрос отклонен. Объявление возвращено в Маркет.")
    await callback.answer()