import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models import Chunk, File, Job, Result
from app.repository.chunk_repository import ChunkRepository
from app.repository.job_repository import JobRepository
from app.repository.result_repository import ResultRepository
from app.service.chunk_service import ChunkService
from app.service.hwpx_service import HwpxService
from app.service.pdf_service import PdfService
from app.service.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)

# 확장자 → 서비스 매핑
FORMAT_SERVICE_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".hwp": "hwpx",   # 레거시 HWP는 hwpx 서비스에서 에러 처리
    ".hwpx": "hwpx",
}


class JobService:
    def __init__(self):
        self.pdf_service = PdfService()
        self.hwpx_service = HwpxService()
        self.chunk_service = ChunkService()
        self.normalizer = TextNormalizer()

    async def recover_orphaned_jobs(self, db: AsyncSession) -> int:
        repo = JobRepository(db)
        orphaned = await repo.get_orphaned_jobs()
        count = 0
        for job in orphaned:
            job.status = "FAILED"
            job.error_message = "서버 재시작으로 인한 작업 중단"
            job.finished_at = datetime.utcnow()
            await repo.update(job)
            count += 1
        logger.info(f"Recovered {count} orphaned jobs")
        return count

    def _extract(self, file_obj: File, job: Job) -> dict:
        """파일 확장자에 따라 적절한 서비스로 추출을 수행한다."""
        ext = (file_obj.file_extension or "").lower()
        service_key = FORMAT_SERVICE_MAP.get(ext)

        if service_key == "hwpx":
            return self.hwpx_service.extract(file_path=file_obj.storage_path)
        elif service_key == "pdf" or service_key is None:
            # 기본값: PDF 서비스
            return self.pdf_service.extract(
                file_path=file_obj.storage_path,
                ocr_enabled=job.ocr_enabled,
                ocr_languages=job.ocr_languages,
                use_hybrid=job.use_hybrid,
            )
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext}")

    async def process_job(self, job_id: UUID, db: AsyncSession) -> None:
        """파일 형식에 따라 적절한 서비스로 작업을 처리한다."""
        job_repo = JobRepository(db)
        result_repo = ResultRepository(db)
        chunk_repo = ChunkRepository(db)

        job = await job_repo.get_by_id(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            job.status = "PROCESSING"
            job.started_at = datetime.utcnow()
            await job_repo.update(job)

            # 파일 형식에 따라 추출
            file_obj = await db.get(File, job.file_id)
            extraction = self._extract(file_obj, job)

            # Update page count
            if extraction.get("page_count"):
                file_obj.page_count = extraction["page_count"]
                await db.commit()

            # Normalize text for RAG/search
            normalized_text = self.normalizer.normalize(extraction["text"])
            normalized_markdown = self.normalizer.normalize(extraction["markdown"])

            # Save result
            result = Result(
                job_id=job.id,
                file_id=job.file_id,
                content_text=normalized_text,
                content_markdown=normalized_markdown,
                content_json=extraction.get("json_raw", extraction["json"]),
            )
            result = await result_repo.create(result)

            # Chunk (정규화된 텍스트 기반으로 청킹)
            if job.chunking_strategy == "semantic":
                raw_chunks = self.chunk_service.chunk_semantic(extraction["json"])
            elif job.chunking_strategy == "fixed":
                raw_chunks = self.chunk_service.chunk_fixed(
                    normalized_text, job.chunk_size or 500, job.chunk_overlap or 50
                )
            else:  # hybrid
                raw_chunks = self.chunk_service.chunk_hybrid(
                    extraction["json"], job.chunk_size or 500, job.chunk_overlap or 50
                )

            # Save chunks (청크 내용도 정규화)
            chunk_models = [
                Chunk(
                    result_id=result.id,
                    chunk_index=i,
                    content=self.normalizer.normalize(c["content"]),
                    token_count=c["token_count"],
                    page_start=c.get("page_start"),
                    page_end=c.get("page_end"),
                    heading=c.get("heading"),
                )
                for i, c in enumerate(raw_chunks)
            ]
            if chunk_models:
                await chunk_repo.create_many(chunk_models)

            job.status = "COMPLETED"
            job.finished_at = datetime.utcnow()
            await job_repo.update(job)

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job.status = "FAILED"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await job_repo.update(job)

    async def process_pdf(self, job_id: UUID, db: AsyncSession) -> None:
        """하위 호환성을 위한 래퍼. process_job으로 위임."""
        await self.process_job(job_id, db)
