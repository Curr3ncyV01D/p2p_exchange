from aiogram import Router, types, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.user import User
from src.database.repository.ad_repo import AdRepository
from src.bot.keyboards.reply import main_menu_kb
from src.bot.utils.ui_helpers import UIHelper

router = Router()

@router.message(CommandStart())
async def cmd_start(
    message: types.Message, 
    command: CommandObject,
    user: User, 
    db_session: AsyncSession, 
    bot_username: str
):
    # Проверяем наличие аргументов в команде /start
    if command.args and command.args.startswith("ad_"):
        await message.delete()
        public_id = command.args.replace("ad_", "")
        ad_repo = AdRepository(db_session)
        ad_info = await ad_repo.get_ad_full_info(public_id)
        
        if not ad_info:
            return await message.answer("❌ Объявление не найдено.")
        
        ad, owner = ad_info
        
        if owner.id == user.id:
            text, kb = UIHelper.get_owner_ad_view(ad, bot_username)
        else:
            text, kb = UIHelper.get_guest_ad_view(ad, owner, bot_username)
            
        return await message.answer(
            text, 
            reply_markup=kb,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

    # Обычный /start без параметров
    await message.answer(
        f"👋 Приветствуем на бирже, <b>{user.display_name}</b>!\n\n"
        f"Это анонимная P2P площадка для обмена <b>Вон — Рубль</b>.\n"
        f"Ваш текущий рейтинг: ⭐ {user.rating}\n\n"
        f"Используйте меню внизу для работы с объявлениями.", 
        reply_markup=main_menu_kb())
