from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.ad import Ad, AdStatus, Currency
from src.database.models.user import User
from sqlalchemy import update, select, func

class AdRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ad(self, user_id: int, public_id: str, requisite_id: int, data: dict):
        new_ad = Ad(
            public_id=public_id,
            user_id=user_id,
            requisite_id=requisite_id,
            base_currency=Currency(data['base_currency']),
            quote_currency=Currency(data['target_currency']),
            min_limit=float(data['min_limit']),
            max_limit=float(data['max_limit']),
            rate=float(data['rate']),
            bank=data['bank'],
            status=AdStatus.ACTIVE
        )
        self.session.add(new_ad)
        await self.session.commit()

    async def get_active_banks(self, base_curr: str, target_curr: str, exclude_user_id: int):
        """Возвращает банки, где есть объявления по конкретной паре"""
        query = (
            select(Ad.bank, func.count(Ad.id))
            .where(
                Ad.status == AdStatus.ACTIVE,
                Ad.base_currency == Currency(base_curr),
                Ad.quote_currency == Currency(target_curr),
                Ad.user_id != exclude_user_id
            )
            .group_by(Ad.bank)
        )
        result = await self.session.execute(query)
        return result.all()

    async def get_market_ads(self, base_curr: str, target_curr: str, bank: str, exclude_user_id: int):
        """Возвращает объявления по паре и банку"""
        query = (
            select(Ad, User)
            .join(User, Ad.user_id == User.id)
            .where(
                Ad.status == AdStatus.ACTIVE,
                Ad.base_currency == Currency(base_curr),
                Ad.quote_currency == Currency(target_curr),
                Ad.bank == bank,
                Ad.user_id != exclude_user_id
            )
            .order_by(Ad.rate.asc()) # По умолчанию сортировка по лучшему курсу
        )
        result = await self.session.execute(query)
        return result.all()

    async def get_ad_full_info(self, public_id: str):
        """Возвращает полную информацию об объявлении и его владельце"""
        query = (
            select(Ad, User)
            .join(User, Ad.user_id == User.id)
            .where(Ad.public_id == public_id)
        )
        result = await self.session.execute(query)
        return result.one_or_none()

    async def get_ad_full_info_by_id(self, ad_id: int):
        """Возвращает полную информацию об объявлении и его владельце по ID"""
        query = (
            select(Ad, User)
            .join(User, Ad.user_id == User.id)
            .where(Ad.id == ad_id)
        )
        result = await self.session.execute(query)
        return result.one_or_none()

    async def try_reserve_ad(self, public_id: str) -> Ad | None:
        """
        Атомарно пытается перевести объявление из ACTIVE в PENDING.
        Если объявление уже занято или удалено, вернет None.
        Это защита от Race Condition.
        """
        query = (
            update(Ad)
            .where(
                Ad.public_id == public_id, 
                Ad.status == AdStatus.ACTIVE
            )
            .values(status=AdStatus.PENDING)
            .returning(Ad)  # Возвращаем объект, если обновление произошло
        )
        
        result = await self.session.execute(query)
        await self.session.commit()
        
        return result.scalar_one_or_none()

    async def update_ad_status(self, public_id: str, new_status: AdStatus):
        """Обновляет статус объявления"""
        query = update(Ad).where(Ad.public_id == public_id).values(status=new_status)
        await self.session.execute(query)
        await self.session.commit()
    
    async def update_ad_status_by_id(self, ad_id: int, new_status: AdStatus):
        query = update(Ad).where(Ad.id == ad_id).values(status=new_status)
        await self.session.execute(query)
        await self.session.commit()
    
    async def get_user_ads(self, user_id: int):
        """Получить все объявления пользователя (активные и скрытые)"""
        query = (
            select(Ad)
            .where(
                Ad.user_id == user_id,
                Ad.status.in_([AdStatus.ACTIVE, AdStatus.HIDDEN]) # Архивы не показываем
            )
            .order_by(Ad.id.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def toggle_ad_visibility(self, public_id: str, user_id: int, is_admin: bool = False) -> Ad | None:
        """Переключить статус ACTIVE <-> HIDDEN"""
        # Сначала находим объявление
        query = select(Ad).where(Ad.public_id == public_id)
        if not is_admin:
            query = query.where(Ad.user_id == user_id)
            
        result = await self.session.execute(query)
        ad = result.scalar_one_or_none()

        if ad:
            if ad.status == AdStatus.ACTIVE:
                ad.status = AdStatus.HIDDEN
            elif ad.status == AdStatus.HIDDEN:
                ad.status = AdStatus.ACTIVE
            
            await self.session.commit()
            return ad
        return None

    async def archive_ad(self, public_id: str, user_id: int, is_admin: bool = False) -> Ad | None:
        """Мягкое удаление объявления (перевод в архив)"""
        # Сначала находим объявление, чтобы вернуть его объект для уведомлений
        query = select(Ad).where(Ad.public_id == public_id)
        if not is_admin:
            query = query.where(Ad.user_id == user_id)
            
        result = await self.session.execute(query)
        ad = result.scalar_one_or_none()
        
        if ad:
            ad.status = AdStatus.ARCHIVED
            await self.session.commit()
            return ad
        return None