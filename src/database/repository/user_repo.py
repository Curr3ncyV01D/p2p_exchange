from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from src.database.models.user import User
from src.database.models.requisite import UserRequisite

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Получить объект пользователя по ID"""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_user_by_display_name(self, name: str) -> User | None:
        """Получить объект пользователя по анонимному имени"""
        result = await self.session.execute(
            select(User).where(User.display_name == name)
        )
        return result.scalar_one_or_none()

    async def get_user_requisites(self, user_id: int) -> list[UserRequisite]:
        """Получить все реквизиты пользователя"""
        result = await self.session.execute(
            select(UserRequisite).where(UserRequisite.user_id == user_id)
        )
        return result.scalars().all()

    async def get_requisite_by_id(self, req_id: int) -> UserRequisite | None:
        """Получить один реквизит по ID"""
        result = await self.session.execute(
            select(UserRequisite).where(UserRequisite.id == req_id)
        )
        return result.scalar_one_or_none()

    async def add_requisite(self, user_id: int, bank_name: str, details: str) -> UserRequisite:
        """Добавить новую карту"""
        new_req = UserRequisite(user_id=user_id, bank_name=bank_name, details=details)
        self.session.add(new_req)
        await self.session.commit()
        return new_req
        
    async def delete_requisite(self, req_id: int, user_id: int):
        """Удалить карту"""
        await self.session.execute(
            delete(UserRequisite).where(
                UserRequisite.id == req_id, 
                UserRequisite.user_id == user_id)
        )
        await self.session.commit()
    
    async def increment_deal_count(self, user_ids: list[int]):
        """Увеличивает количество сделок для списка ID пользователей"""
        from sqlalchemy import update
        query = (
            update(User)
            .where(User.id.in_(user_ids))
            .values(deal_count=User.deal_count + 1)
        )
        await self.session.execute(query)
        await self.session.commit()