from src.database.models.user import User
from src.core.constants import ReputationConfig as Config

def get_user_badges(user: User) -> str:
    """
    Генерирует строку тегов на основе бизнес-правил.
    Логика: Reliable поглощает Verified. Conflict — приоритетный ворнинг.
    """
    badges = []

    # 1. Проверка на конфликты (негативный статус всегда первый)
    if user.conflict_strikes > 0:
        badges.append("⚠️ Был Конфликт")

    # 2. Определение уровня доверия (Иерархия: Reliable > Verified)
    is_reliable = (
        user.is_verified and 
        user.deal_count >= Config.RELIABLE_DEALS_THRESHOLD and 
        user.rating >= Config.RELIABLE_RATING_THRESHOLD
    )

    if is_reliable:
        badges.append("🔥 Надежный")
    elif user.is_verified:
        badges.append("✅ Проверен")

    # 3. Маркер новичка
    if user.deal_count < Config.NEWBIE_DEALS_THRESHOLD:
        badges.append("🆕 Новичок")

    return " | ".join(badges) if badges else ""