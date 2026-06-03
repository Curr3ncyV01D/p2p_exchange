from src.database.models.deal import DealStatus

CURRENCY_NOMINALS = { 
    "KRW": 1000, 
    "RUB": 1, 
    "KZT": 100, 
} 

DEAL_STATUS_NAMES = {
    DealStatus.WAITING_BUYER_PAY: "💳 Ожидание оплаты покупателем",
    DealStatus.WAITING_SELLER_CONFIRM: "🧐 Проверка оплаты продавцом",
    DealStatus.WAITING_SELLER_PAY: "💸 Оплата от продавца",
    DealStatus.WAITING_BUYER_CONFIRM: "🧐 Проверка получения покупателем",
    DealStatus.COMPLETED: "✅ Завершена",
    DealStatus.CANCELLED: "❌ Отменена",
    DealStatus.DISPUTED: "⚖️ В споре"
}

class ReputationConfig:
    RELIABLE_DEALS_THRESHOLD = 50
    RELIABLE_RATING_THRESHOLD = 4.8
    NEWBIE_DEALS_THRESHOLD = 5