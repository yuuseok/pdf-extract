from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models import File


class FileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, file: File) -> File:
        self.db.add(file)
        await self.db.commit()
        await self.db.refresh(file)
        return file

    async def get_by_id(self, file_id: UUID) -> File | None:
        result = await self.db.execute(select(File).where(File.id == file_id))
        return result.scalar_one_or_none()

    async def get_list(self, page: int, per_page: int) -> tuple[list[File], int]:
        total_result = await self.db.execute(select(func.count()).select_from(File))
        total = total_result.scalar()

        offset = (page - 1) * per_page
        result = await self.db.execute(
            select(File).order_by(File.created_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def delete(self, file: File) -> None:
        await self.db.delete(file)
        await self.db.commit()

    async def update(self, file: File) -> File:
        await self.db.commit()
        await self.db.refresh(file)
        return file
