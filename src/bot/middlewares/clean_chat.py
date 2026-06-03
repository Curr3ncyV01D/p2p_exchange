from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

class CleanReplyMiddleware(BaseMiddleware):
    def __init__(self):
        # Список текстов кнопок, которые мы хотим удалять после нажатия
        self.reply_commands = {"📈 Маркет", "👤 Мой профиль", "📢 Мои объявления", "💼 Мои сделки"}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.text:
            if event.text in self.reply_commands:
                try:
                    await event.delete()
                except Exception:
                    pass
        
        return await handler(event, data)