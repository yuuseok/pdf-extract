from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models import Chunk


class ChunkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_many(self, chunks: list[Chunk]) -> list[Chunk]:
        self.db.add_all(chunks)
        await self.db.commit()
        return chunks

    async def get_by_result_id(
        self, result_id: UUID, page: int, per_page: int
    ) -> tuple[list[Chunk], int]:
        total_result = await self.db.execute(
            select(func.count()).select_from(Chunk).where(Chunk.result_id == result_id)
        )
        total = total_result.scalar()

        offset = (page - 1) * per_page
        result = await self.db.execute(
            select(Chunk)
            .where(Chunk.result_id == result_id)
            .order_by(Chunk.chunk_index.asc())
            .offset(offset)
            .limit(per_page)
        )
        return list(result.scalars().all()), total
