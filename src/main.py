import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis
from src.services.scheduler_service import SchedulerService
from src.bot.instance import set_bot

from src.core.config import config
from src.bot import routers, middlewares

async def main():
    # 1. Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)

    # 2. Инициализация Redis (для FSM)
    redis = Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=True
    )
    storage = RedisStorage(redis)

    # 3. Инициализация бота и диспетчера

    session = None
    if config.PROXY_URL:
        print(config.PROXY_URL)
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=config.PROXY_URL)
        logging.info(f"📡 Запуск с прокси: {config.PROXY_URL}")
    else:
        logging.info("🌐 Запуск без прокси (прямое соединение)")
    
    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
    )
    set_bot(bot)

    bot_info = await bot.get_me()

    # Инициилизируем планировщик
    scheduler_service = SchedulerService(bot)
    scheduler_service.start()

    dp = Dispatcher(storage=storage,
                    scheduler=scheduler_service,
                    bot_username=bot_info.username)

    # 4. Подключение роутеров и middleware
    for router in routers:
        dp.include_router(router)

    for middleware_class, scopes in middlewares:
        instance = middleware_class()  # Создаем экземпляр один раз
        for scope in scopes:
            # Получаем dp.message или dp.callback_query динамически
            observer = getattr(dp, scope)
            observer.middleware(instance)

    # 5. Запуск polling
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Bot stopped!")