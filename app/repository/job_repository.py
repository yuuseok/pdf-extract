from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models import Job


class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, job: Job) -> Job:
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Job | None:
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def get_by_file_id(self, file_id: UUID) -> list[Job]:
        result = await self.db.execute(
            select(Job).where(Job.file_id == file_id).order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_by_file_id(self, file_id: UUID) -> list[Job]:
        result = await self.db.execute(
            select(Job).where(
                Job.file_id == file_id,
                Job.status.in_(["PENDING", "PROCESSING"])
            )
        )
        return list(result.scalars().all())

    async def get_orphaned_jobs(self) -> list[Job]:
        result = await self.db.execute(
            select(Job).where(Job.status == "PROCESSING")
        )
        return list(result.scalars().all())

    async def update(self, job: Job) -> Job:
        await self.db.commit()
        await self.db.refresh(job)
        return job
