from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.profile import ProfileKeyboards
from src.bot.states.profile import RequisiteStates
from src.database.repository.user_repo import UserRepository
from src.database.models.user import User
from src.bot.utils.gen_badges import get_user_badges



router = Router()

def _get_profile_text(user: User, reqs_count: int) -> str:
    badges = get_user_badges(user)
    badges_line = f"🏷 Статус: <b>{badges}</b>\n" if badges else ""
    
    return (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 Анонимный ник: <code>{user.display_name}</code>\n"
        f"{badges_line}"
        f"⭐ Рейтинг: {user.rating} ({user.deal_count} сделок)\n"
        f"💳 Сохраненных реквизитов: <b>{reqs_count}</b>\n\n"
        f"<i>Администрация видит ваш реальный ID только в случае споров.</i>"
    )

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message, user: User, db_session: AsyncSession):
    repo = UserRepository(db_session)
    reqs = await repo.get_user_requisites(user.id)
    
    text = _get_profile_text(user, len(reqs))
    await message.answer(text, reply_markup=ProfileKeyboards.get_profile_keyboard(user.is_admin))

@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery, user: User, db_session: AsyncSession):
    repo = UserRepository(db_session)
    reqs = await repo.get_user_requisites(user.id)
    
    text = _get_profile_text(user, len(reqs))
    await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_profile_keyboard(user.is_admin))
    await callback.answer()

@router.callback_query(F.data == "my_requisites")
async def show_requisites(callback: types.CallbackQuery, db_session: AsyncSession):
    repo = UserRepository(db_session)
    reqs = await repo.get_user_requisites(callback.from_user.id)
    
    text = "💳 <b>Ваши сохраненные реквизиты:</b>\n\n"
    
    if not reqs:
        text += "У вас пока нет сохраненных реквизитов."
    else:
        for i, req in enumerate(reqs, 1):
            text += f"{i}. <b>{req.bank_name}</b>: <code>{req.details}</code>\n"
            # Можно добавить кнопку удаления, но для MVP пропустим
            
    await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_requisites_keyboard())

@router.callback_query(F.data == "add_requisite")
async def start_add_requisite(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название банка (например: <i>Сбербанк</i> или <i>Woori</i>):")
    await state.set_state(RequisiteStates.waiting_for_bank_name)

@router.message(RequisiteStates.waiting_for_bank_name)
async def process_bank_name(message: types.Message, state: FSMContext):
    await state.update_data(bank_name=message.text)
    await message.answer("Введите реквизиты (номер карты, телефон или счет):")
    await state.set_state(RequisiteStates.waiting_for_details)

@router.message(RequisiteStates.waiting_for_details)
async def process_details(message: types.Message, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    repo = UserRepository(db_session)
    
    await repo.add_requisite(message.from_user.id, data['bank_name'], message.text)

    await message.answer("✅ Реквизиты успешно добавлены! Перейдите в профиль, чтобы посмотреть их.")
    await state.clear()