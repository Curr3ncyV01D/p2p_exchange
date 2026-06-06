from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.repository.user_repo import UserRepository
from src.database.models.user import User
from src.database.models.deal import Deal, DealStatus
from src.database.models.dispute import Dispute
from src.database.models.ad import Ad, AdStatus
from src.database.models.verification import VerificationRequest, VerificationStatus

class AdminService:
    def __init__(self, session: AsyncSession, repo: UserRepository):
        self.session = session
        self.repo = repo
    
    async def resolve_verification(self, request_id: int, action: str) -> tuple[VerificationRequest | None, User | None]:
        """Одобрение или отклонение заявки на верификацию"""
        query = select(VerificationRequest).where(VerificationRequest.id == request_id)
        result = await self.session.execute(query)
        verification = result.scalar_one_or_none()
        
        if not verification:
            return None, None
            
        user = await self.repo.get_user_by_id(verification.user_id)
        if not user:
            return None, None
            
        if action == "approve":
            user.is_verified = True
            verification.status = VerificationStatus.COMPLETED
        else:
            verification.status = VerificationStatus.DECLINED
            
        await self.session.commit()
        return verification, user

    async def resolve_dispute(self, dispute_id: int, resolution: str):
        """Закрытие спора арбитром или пользователем"""
        # 1. Находим спор
        dispute_stmt = select(Dispute).where(Dispute.id == dispute_id)
        result = await self.session.execute(dispute_stmt)
        dispute = result.scalar_one_or_none()
        
        if not dispute:
            return None, None

        # 2. Находим сделку
        deal_stmt = select(Deal).where(Deal.id == dispute.deal_id)
        result = await self.session.execute(deal_stmt)
        deal = result.scalar_one_or_none()

        if not deal:
            return None, None

        # 3. Применяем решение и начисляем страйки (если не мирное решение)
        is_amicable = resolution.startswith("amicable_")
        action = resolution.replace("amicable_", "")

        if action == "complete":
            # Победа покупателя -> Сделка завершена
            deal.status = DealStatus.COMPLETED
            if not is_amicable:
                seller = await self.repo.get_user_by_id(deal.seller_id)
                if seller:
                    seller.conflict_strikes += 1
        
        elif action == "cancel":
            # Победа продавца -> Сделка отменена
            deal.status = DealStatus.CANCELLED
            if not is_amicable:
                buyer = await self.repo.get_user_by_id(deal.buyer_id)
                if buyer:
                    buyer.conflict_strikes += 1

        # 4. Возвращаем объявление в маркет
        if deal.ad_id:
            ad_stmt = select(Ad).where(Ad.id == deal.ad_id)
            result = await self.session.execute(ad_stmt)
            ad = result.scalar_one_or_none()
            if ad:
                ad.status = AdStatus.ACTIVE

        # 5. Закрываем спор
        dispute.status = "closed"
        
        await self.session.commit()
        return deal, dispute

    async def search_user(self, query: str) -> User | None:
        """Поиск пользователя по ID (если число) или по Нику"""
        query = query.strip()
        
        if query.isdigit():
            return await self.repo.get_user_by_id(int(query))
        
        return await self.repo.get_user_by_display_name(query)

    async def toggle_verify(self, user_id: int):
        user = await self.repo.get_user_by_id(user_id)
        if user:
            user.is_verified = not user.is_verified
            await self.session.commit()
        return user
    
    async def toggle_banned(self, user_id: int):
        user = await self.repo.get_user_by_id(user_id)
        if user:
            user.is_banned = not user.is_banned
            await self.session.commit()
        return user