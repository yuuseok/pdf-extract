from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models import Result


class ResultRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, result: Result) -> Result:
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        return result

    async def get_by_job_id(self, job_id: UUID) -> Result | None:
        result = await self.db.execute(select(Result).where(Result.job_id == job_id))
        return result.scalar_one_or_none()
