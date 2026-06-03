from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.review import Review
from src.database.models.user import User

class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_review(self, deal_id: int, from_user_id: int, to_user_id: int, score: int):
        """Добавляет отзыв и инициирует пересчет рейтинга"""
        # Проверяем, не оставлял ли уже этот юзер отзыв по этой сделке
        exists_query = select(Review).where(
            Review.deal_id == deal_id, 
            Review.from_user_id == from_user_id
        )
        result = await self.session.execute(exists_query)
        if result.scalar_one_or_none():
            return False

        new_review = Review(
            deal_id=deal_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            score=score
        )
        self.session.add(new_review)
        await self.session.commit()
        
        # После добавления обновляем глобальную статистику пользователя
        await self._update_user_stats(to_user_id)
        return True

    async def _update_user_stats(self, user_id: int):
        """Пересчитывает ТОЛЬКО рейтинг на основе имеющихся отзывов"""
        # Считаем средний балл (AVG игнорирует отсутствие записей, 
        # поэтому если отзывов нет, рейтинг не изменится)
        avg_query = select(func.avg(Review.score)).where(Review.to_user_id == user_id)
        avg_res = await self.session.execute(avg_query)
        new_rating = avg_res.scalar()

        if new_rating is not None:
            await self.session.execute(
                update(User)
                .where(User.id == user_id)
                .values(rating=float(round(new_rating, 2)))
            )
            await self.session.commit()