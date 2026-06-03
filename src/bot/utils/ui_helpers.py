from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models.ad import Ad, AdStatus
from src.database.models.user import User
from src.bot.utils.gen_badges import get_user_badges
from src.bot.utils.formatter import format_number
from src.core.constants import CURRENCY_NOMINALS


class UIHelper:
    @staticmethod
    def get_ad_link(bot_username: str, public_id: str) -> str:
        """Генерирует HTML-ссылку на объявление в формате #HASH"""
        link = f"https://t.me/{bot_username}?start=ad_{public_id}"
        return f'<a href="{link}">#{public_id}</a>'

    @staticmethod
    def get_owner_ad_view(ad: Ad, bot_username: str, back_data: str = None) -> tuple[str, InlineKeyboardMarkup]:
        """Генерирует текст и клавиатуру для владельца при просмотре объявления по ссылке"""
        if ad.status == AdStatus.ACTIVE:
            emoji = "🟢"
        elif ad.status == AdStatus.PENDING:
            emoji = "✉"
        else:
            emoji = "⚪"
        ad_link = UIHelper.get_ad_link(bot_username, ad.public_id)
        
        text = (
            f"📢 <b>Управление объявлением {ad_link}</b>\n\n"
            f"Статус: {emoji} {ad.status.value.upper()}\n"
            f"Пара: <b>{ad.base_currency.value} / {ad.quote_currency.value}</b>\n"
            f"Курс: <b>{format_number(ad.rate)}</b>\n"
            f"Лимиты: {format_number(ad.min_limit)} - {format_number(ad.max_limit)} {ad.base_currency.value}\n"
            f"Банк: {ad.bank}\n"
        )
        
        builder = InlineKeyboardBuilder()
        toggle_text = "👁 Показать" if ad.status == AdStatus.HIDDEN else "🙈 Скрыть"
        builder.row(InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_ad_{ad.public_id}"))
        builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"archive_ad_{ad.public_id}"))
        
        # Если back_data не передан, используем переход к списку моих объявлений по умолчанию
        UIHelper.add_common_buttons(builder, back_data=back_data or "back_to_my_ads")
        
        return text, builder.as_markup()

    @staticmethod
    def get_guest_ad_view(ad: Ad, owner: User, bot_username: str, back_data: str = None) -> tuple[str, InlineKeyboardMarkup]:
        """Генерирует текст и клавиатуру для гостя (покупателя) при просмотре объявления по ссылке"""
        ad_link = UIHelper.get_ad_link(bot_username, ad.public_id)
        nominal = CURRENCY_NOMINALS.get(ad.base_currency.value, 1)

        badges = get_user_badges(owner)
        badges_text = f"\n🏷 Статус: <b>{badges}</b>" if badges else ""
        
        text = (
            f"📄 <b>Объявление {ad_link}</b>\n\n"
            f"👤 Владелец: <b>{owner.display_name}</b>{badges_text}\n"
            f"⭐ Рейтинг: <code>{owner.rating}</code> ({owner.deal_count} сделок)\n\n"
            f"🔄 Обмен: <b>{ad.base_currency.value}</b> за <b>{ad.quote_currency.value}</b>\n"
            f"💰 Курс: <b>{format_number(ad.rate)} {ad.quote_currency.value}</b> за {nominal} {ad.base_currency.value}\n"
            f"📏 Лимиты: <b>{format_number(ad.min_limit)} - {format_number(ad.max_limit)} {ad.base_currency.value}</b>\n"
            f"🏦 Банк: <b>{ad.bank}</b>\n\n"
        )
        
        builder = InlineKeyboardBuilder()
        if ad.status == AdStatus.ACTIVE:
            text += "<i>Нажмите кнопку ниже, чтобы начать сделку.</i>"
            builder.row(InlineKeyboardButton(text="🤝 Начать сделку", callback_data=f"start_deal_{ad.public_id}"))
        elif ad.status == AdStatus.HIDDEN:
            text += "⚠️ <b>Объявление временно скрыто владельцем.</b>"
        elif ad.status == AdStatus.ARCHIVED:
            text += "🗄 <b>Это объявление в архиве.</b>\nНачать сделку нельзя."
            
        # Если back_data не передан, используем переход в маркет по умолчанию
        UIHelper.add_common_buttons(builder, back_data=back_data or "back_to_market")
        
        return text, builder.as_markup()

    @staticmethod
    def format_admin_user_view(target_user: User) -> str:
        """Карточка пользователя для админа"""
        badges = get_user_badges(target_user)
        status_emoji = "🔴 ЗАБАНЕН" if target_user.is_banned else "🟢 Активен"
        
        return (
            f"🛠 <b>Управление пользователем</b>\n\n"
            f"Ник: <code>{target_user.display_name}</code>\n"
            f"Статус: <b>{badges or 'Обычный'}</b>\n"
            f"ID: <code>{target_user.id}</code>\n\n"
            f"Состояние: {status_emoji}\n"
            f"Сделок: {target_user.deal_count} | Рейтинг: {target_user.rating}\n"
            f"Конфликтов: {target_user.conflict_strikes}"
        )

    @staticmethod
    def add_common_buttons(
        builder: InlineKeyboardBuilder, 
        back_data: str = None, 
        close: bool = True
    ):
        """
        Добавляет стандартные кнопки в конец клавиатуры.
        :param builder: Текущий объект InlineKeyboardBuilder
        :param back_data: callback_data для кнопки Назад (если нужна)
        :param close: Добавлять ли кнопку Закрыть
        """
        # Если нужна кнопка Назад, добавляем её в новый ряд
        if back_data:
            builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_data))
        
        # Если нужна кнопка Закрыть, добавляем её (в новый ряд или к кнопке Назад)
        if close:
            # .row() гарантирует, что кнопка будет на новой строке
            builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="common_close"))
        
        return builder