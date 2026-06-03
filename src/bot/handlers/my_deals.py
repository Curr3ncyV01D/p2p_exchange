from aiogram import Router, F, types, Bot
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.bot.utils.formatter import format_number
from src.core.constants import DEAL_STATUS_NAMES

from src.database.repository.deal_repo import DealRepository
from src.database.repository.user_repo import UserRepository
from src.database.repository.ad_repo import AdRepository
from src.database.models.deal import DealStatus
from src.database.models.user import User
from src.bot.utils.ui_helpers import UIHelper
from src.bot.keyboards.deals import DealKeyboards

router = Router()

@router.message(F.text == "💼 Мои сделки")
async def list_my_deals(message: types.Message, user: User, db_session: AsyncSession):
    deal_repo = DealRepository(db_session)
    deals = await deal_repo.get_active_deals_by_user(user.id)
    
    builder = InlineKeyboardBuilder()

    if not deals:
        UIHelper.add_common_buttons(builder)
        return await message.answer("💼 <b>Мои сделки</b>\n\nУ вас нет активных сделок на данный момент.",
        reply_markup=builder.as_markup())
    
    for deal in deals:
        role = "Покупатель" if deal.buyer_id == user.id else "Продавец"
        btn_text = f"🤝 Сделка #{deal.public_id} | {role}"
        builder.row(types.InlineKeyboardButton(text=btn_text, callback_data=f"restore_deal_{deal.public_id}"))
        
    UIHelper.add_common_buttons(builder)
    await message.answer(
        "💼 <b>Активные сделки</b>\n\nВыберите сделку для продолжения работы:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("restore_deal_"))
async def restore_deal_context(callback: types.CallbackQuery, user: User, db_session: AsyncSession, bot: Bot):
    public_id = callback.data.replace("restore_deal_", "")
    deal_repo = DealRepository(db_session)
    user_repo = UserRepository(db_session)
    ad_repo = AdRepository(db_session)
    
    deal = await deal_repo.get_deal_by_public_id(public_id)
    if not deal or (deal.buyer_id != user.id and deal.seller_id != user.id):
        return await callback.answer("❌ Сделка не найдена или вы не являетесь её участником.", show_alert=True)
    
    status = deal.status
    is_buyer = deal.buyer_id == user.id
    is_seller = deal.seller_id == user.id

    # Получаем информацию об объявлении для курсов и валют
    ad_info = await ad_repo.get_ad_full_info_by_id(deal.ad_id)
    ad, _ = ad_info
    
    # Текст общих параметров сделки
    status_name = DEAL_STATUS_NAMES.get(status, status.value.upper())
    
    text_common = (
        f"🤝 <b>Сделка #{deal.public_id}</b>\n"
        f"Сумма: {format_number(deal.amount_base)} {ad.base_currency.value} 🔄 {format_number(deal.amount_quote)} {ad.quote_currency.value}\n"
        f"Курс: <b>{format_number(ad.rate)}</b>\n"
        f"Статус: <b>{status_name}</b>\n\n"
    )

    # ЛОГИКА SMART RESTORE С ФОТО ЧЕКОВ
    
    # 1. Ожидание оплаты от Покупателя (Тейкера)
    if status == DealStatus.WAITING_BUYER_PAY:
        if is_buyer:
            maker_req = await user_repo.get_requisite_by_id(ad.requisite_id)
            text = text_common + (
                f"💳 Переведите <b>{format_number(deal.amount_quote)} {ad.quote_currency.value}</b> на реквизиты:\n"
                f"Банк: {maker_req.bank_name}\n"
                f"Данные: <code>{maker_req.details}</code>\n\n"
                f"⏳ После оплаты пришлите фото чека."
            )
            await callback.message.edit_text(text)
        else:
            await callback.message.edit_text(text_common + "⏳ Ожидайте оплату от покупателя.")

    # 2. Ожидание подтверждения от Продавца (Мейкера)
    elif status == DealStatus.WAITING_SELLER_CONFIRM:
        if is_seller:
            # Продавец видит чек покупателя
            await bot.send_photo(
                chat_id=user.id,
                photo=deal.buyer_receipt_id,
                caption=text_common + "🔔 Покупатель прикрепил чек. Проверьте поступление!",
                reply_markup=DealKeyboards.confirm_receipt_maker(deal.public_id)
            )
            await callback.message.delete()
        else:
            await bot.send_message(
                chat_id=user.id,
                text=text_common + "⏳ Ожидайте, пока продавец подтвердит получение средств."
            )
            await callback.message.delete()

    # 3. Ожидание оплаты от Продавца (Мейкера)
    elif status == DealStatus.WAITING_SELLER_PAY:
        if is_seller:
            taker_req = await user_repo.get_requisite_by_id(deal.requisite_id)
            text = text_common + (
                f"Теперь ваша очередь! Переведите средства Тейкеру:\n"
                f"Банк: <b>{taker_req.bank_name}</b>\n"
                f"Реквизиты: <code>{taker_req.details}</code>\n\n"
                f"⏳ Пришлите фото чека после перевода."
            )
            # Если уже есть чек покупателя, показываем его
            if deal.buyer_receipt_id:
                await bot.send_photo(
                    chat_id=user.id,
                    photo=deal.buyer_receipt_id,
                    caption=text,
                )
                await callback.message.delete()
            else:
                await callback.message.edit_text(text)
        else:
            await callback.message.edit_text(text_common + "✅ Вы оплатили. Теперь продавец переводит средства вам.")

    # 4. Ожидание подтверждения от Покупателя (Тейкера)
    elif status == DealStatus.WAITING_BUYER_CONFIRM:
        if is_buyer:
            # Покупатель видит чек продавца
            await bot.send_photo(
                chat_id=user.id,
                photo=deal.seller_receipt_id,
                caption=text_common + "🔔 Продавец перевел средства. Проверьте баланс!",
                reply_markup=DealKeyboards.confirm_receipt_taker(deal.public_id)
            )
            await callback.message.delete()
        else:
            # Продавец видит чек покупателя
            await bot.send_photo(
                chat_id=user.id,
                photo=deal.buyer_receipt_id,
                caption=text_common + "⏳ Ожидайте, пока покупатель подтвердит получение средств."
            )
            await callback.message.delete()
    
    else:
        await callback.message.edit_text(text_common)

    await callback.answer()
