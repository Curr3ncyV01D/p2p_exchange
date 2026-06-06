from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.verification import VerificationRequest, VerificationStatus
from typing import Optional

class VerificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_request(self, user_id: int) -> VerificationRequest:
        """Создание новой заявки на верификацию"""
        new_request = VerificationRequest(user_id=user_id, status=VerificationStatus.PENDING)
        self.session.add(new_request)
        await self.session.commit()
        await self.session.refresh(new_request)
        return new_request

    async def get_active_request_by_user(self, user_id: int) -> Optional[VerificationRequest]:
        """Поиск активной заявки пользователя (не завершена и не отклонена)"""
        query = (
            select(VerificationRequest)
            .where(
                VerificationRequest.user_id == user_id,
                VerificationRequest.status.in_([VerificationStatus.PENDING, VerificationStatus.ACTIVE])
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_pending_requests(self) -> list[VerificationRequest]:
        """Получение всех заявок в статусе PENDING"""
        query = (
            select(VerificationRequest)
            .where(VerificationRequest.status == VerificationStatus.PENDING)
            .order_by(VerificationRequest.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_request(self, request_id: int, **kwargs) -> Optional[VerificationRequest]:
        """Универсальный метод обновления полей заявки"""
        query = (
            update(VerificationRequest)
            .where(VerificationRequest.id == request_id)
            .values(**kwargs)
            .returning(VerificationRequest)
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def get_request_by_topic_id(self, topic_id: int) -> Optional[VerificationRequest]:
        """Поиск заявки по ID топика в Telegram"""
        query = select(VerificationRequest).where(VerificationRequest.group_topic_id == topic_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
