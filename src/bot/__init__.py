from src.bot.handlers.commands import router as commands_router
from src.bot.handlers.profile import router as profile_router
from src.bot.handlers.common import router as common_router
from src.bot.handlers.ads import router as ads_router
from src.bot.handlers.market import router as market_router
from src.bot.handlers.handshake import router as handshake_router
from src.bot.handlers.deals import router as deals_router
from src.bot.handlers.my_ads import router as my_ads_router
from src.bot.handlers.my_deals import router as my_deals_router
from src.bot.handlers.admin import router as admin_router
from src.bot.handlers.dispute import router as dispute_router

from src.bot.middlewares.clean_chat import CleanReplyMiddleware
from src.bot.middlewares.auth import AuthenticatorMiddleware
from src.bot.middlewares.deal_guard import DealGuardMiddleware

deals_router.callback_query.middleware(DealGuardMiddleware())

routers = [
    common_router, 
    commands_router, 
    profile_router, 
    ads_router, 
    market_router, 
    handshake_router, 
    deals_router,
    my_ads_router,
    my_deals_router,
    admin_router,
    dispute_router
]

middlewares = [
    (AuthenticatorMiddleware, ["message", "callback_query"]),
    (CleanReplyMiddleware, ["message"]),
]
