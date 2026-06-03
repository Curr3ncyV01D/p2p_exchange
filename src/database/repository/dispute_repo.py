from sqlalchemy import select
from src.database.models.dispute import Dispute

class DisputeRepository:
    def __init__(self, session):
        self.session = session

    async def create_dispute(self, deal_id, opened_by_id, reason):
        dispute = Dispute(deal_id=deal_id, opened_by_id=opened_by_id, reason=reason)
        self.session.add(dispute)
        await self.session.commit()
        return dispute

    async def get_dispute_by_topic_id(self, topic_id: int):
        result = await self.session.execute(
            select(Dispute).where(Dispute.group_topic_id == topic_id)
        )
        return result.scalar_one_or_none()