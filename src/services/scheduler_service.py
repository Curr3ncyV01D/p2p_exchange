from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from src.core.config import config
from aiogram import Bot

class SchedulerService:
    def __init__(self, bot: Bot):
        # Храним задачи в Redis, чтобы они не пропадали при перезагрузке
        jobstores = {
            'default': RedisJobStore(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=1 # Используем отдельную БД Redis для задач
            )
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores)
        self.bot = bot

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def add_deal_timeout_job(self, deal_id: int, public_id: str, expires_at):
        """Добавляет задачу на проверку оплаты через 15 минут"""
        from src.services.deal_timeout_worker import check_deal_timeout
        
        self.scheduler.add_job(
            check_deal_timeout,
            trigger='date',
            run_date=expires_at,
            id=f"deal_timeout_{public_id}",
            args=[deal_id, public_id],
            replace_existing=True
        )

    def remove_deal_timeout_job(self, public_id: str):
        """Удаляет задачу (если оплата прошла вовремя)"""
        job_id = f"deal_timeout_{public_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)