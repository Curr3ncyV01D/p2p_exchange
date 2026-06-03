from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, types
from aiogram.types import Message, CallbackQuery
from sqlalchemy.future import select
from src.database.session import async_session
from src.database.models.user import User
from src.services.pseudonym import generate_nickname

class AuthenticatorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not hasattr(event, "from_user") or not event.from_user:
            return await handler(event, data)

        async with async_session() as session:
            # Проверяем, есть ли юзер в базе
            result = await session.execute(
                select(User).where(User.id == event.from_user.id)
            )
            user = result.scalar_one_or_none()

            # Если нет — регистрируем
            if not user:
                user = User(
                    id=event.from_user.id,
                    display_name=generate_nickname()
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            # ПРОВЕРКА БАНА
            if user.is_banned:
                if isinstance(event, Message):
                    await event.answer("🚫 Ваш аккаунт заблокирован. Вы можете обратиться в тех. поддержку.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
                return

            # Передаем объект юзера и сессию дальше в хендлеры
            data["user"] = user
            data["is_admin"] = user.is_admin
            data["db_session"] = session
            
            return await handler(event, data)