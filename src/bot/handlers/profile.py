from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.profile import ProfileKeyboards
from src.bot.states.profile import RequisiteStates
from src.bot.states.verification import VerificationStates
from src.database.repository.user_repo import UserRepository
from src.database.repository.verification_repo import VerificationRepository
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
    v_repo = VerificationRepository(db_session)
    
    reqs = await repo.get_user_requisites(user.id)
    verification = await v_repo.get_active_request_by_user(user.id)
    
    text = _get_profile_text(user, len(reqs))
    await message.answer(text, reply_markup=ProfileKeyboards.get_profile_keyboard(user, verification))

@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery, user: User, db_session: AsyncSession):
    repo = UserRepository(db_session)
    v_repo = VerificationRepository(db_session)
    
    reqs = await repo.get_user_requisites(user.id)
    verification = await v_repo.get_active_request_by_user(user.id)
    
    text = _get_profile_text(user, len(reqs))
    await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_profile_keyboard(user, verification))
    await callback.answer()

@router.callback_query(F.data == "start_verification")
async def start_verification(callback: types.CallbackQuery):
    text = (
        "🌟 <b>Верификация пользователя</b>\n\n"
        "Верификация позволяет получить статус ✅ и открывает доступ к VIP-объявлениям.\n\n"
        "<b>Что это дает?</b>\n"
        "- Повышенное доверие со стороны контрагентов\n"
        "- Возможность откликаться на объявления «Только для верифицированных»\n"
        "- Приоритетная поддержка в случае споров\n\n"
        "<b>Как это проходит?</b>\n"
        "После подачи заявки администратор создаст с вами чат прямо здесь, в боте. "
        "Вам нужно будет предоставить подтверждающие документы или иную информацию по запросу.\n\n"
        "⚠️ <i>Ваши данные не сохраняются в базе и доступны только администратору на время проверки.</i>"
    )
    await callback.message.edit_text(text, reply_markup=ProfileKeyboards.get_verification_confirm_keyboard())
    await callback.answer()

@router.callback_query(F.data == "submit_verification")
async def submit_verification(callback: types.CallbackQuery, user: User, db_session: AsyncSession):
    v_repo = VerificationRepository(db_session)
    
    # 1. Проверка на дубликат
    existing = await v_repo.get_active_request_by_user(user.id)
    if existing:
        return await callback.answer("❌ У вас уже есть активная заявка.", show_alert=True)
    
    if user.is_verified:
        return await callback.answer("✅ Вы уже верифицированы.", show_alert=True)

    # 2. Создаем заявку и получаем её объект
    new_request = await v_repo.create_request(user.id)
    
    text = (
        "✅ <b>Заявка подана!</b>\n\n"
        "Когда администратор освободится, он создаст чат.\n\n"
        "Если вам нужно выйти в меню, пропишите /start — чат временно закроется, но заявка останется активной. "
        "Вернуться в чат можно через Профиль."
    )
    
    await callback.message.edit_text(
        text, 
        reply_markup=ProfileKeyboards.get_profile_keyboard(user, new_request)
    )
    await callback.answer("Заявка успешно подана!")

@router.callback_query(F.data == "open_verification_chat")
async def open_verification_chat(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(VerificationStates.active_verification)
    text = (
        "🔄 <b>Вы вошли в чат верификации.</b>\n\n"
        "Все ваши сообщения здесь будут транслироваться администратору.\n\n"
        "Для выхода в главное меню пропишите /start."
    )
    await callback.message.edit_text(text)
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