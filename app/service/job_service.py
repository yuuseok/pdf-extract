import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.model.models import Chunk, File, Job, Result
from app.repository.chunk_repository import ChunkRepository
from app.repository.job_repository import JobRepository
from app.repository.result_repository import ResultRepository
from app.service.chunk_service import ChunkService
from app.service.pdf_service import PdfService
from app.service.quality_checker import QualityChecker
from app.service.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self):
        self.pdf_service = PdfService()
        self.chunk_service = ChunkService()
        self.normalizer = TextNormalizer()
        self.quality_checker = QualityChecker()

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

    async def process_pdf(self, job_id: UUID, db: AsyncSession) -> None:
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

            file_obj = await db.get(File, job.file_id)

            # 사용자가 직접 옵션을 지정한 경우 → 바로 해당 모드로 실행
            if job.ocr_enabled or job.use_hybrid:
                logger.info(
                    "User specified mode: ocr_enabled=%s, use_hybrid=%s",
                    job.ocr_enabled, job.use_hybrid,
                )
                extraction = self.pdf_service.extract(
                    file_path=file_obj.storage_path,
                    ocr_enabled=job.ocr_enabled,
                    ocr_languages=job.ocr_languages,
                    use_hybrid=job.use_hybrid,
                )
            else:
                # 자동 판단 흐름: 1단계 일반 추출 → 품질 검증 → 필요 시 재처리
                extraction = self._extract_with_auto_reprocess(
                    file_obj, job, job_repo, db
                )

            # Update page count
            if extraction.get("page_count"):
                file_obj.page_count = extraction["page_count"]
                await db.commit()

            # 결과 저장 및 청킹
            await self._save_results_and_chunks(
                extraction, job, result_repo, chunk_repo
            )

            job.status = "COMPLETED"
            job.finished_at = datetime.utcnow()
            await job_repo.update(job)

        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job.status = "FAILED"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await job_repo.update(job)

    def _extract_with_auto_reprocess(
        self, file_obj: File, job: Job, job_repo, db
    ) -> dict:
        """1단계 일반 추출 → 품질 검증 → 필요 시 2단계 재처리."""

        # 1단계: 일반 모드 추출
        logger.info("Step 1: Normal mode extraction for %s", file_obj.storage_path)
        extraction = self.pdf_service.extract(
            file_path=file_obj.storage_path,
            ocr_enabled=False,
            use_hybrid=False,
        )

        page_count = extraction.get("page_count")

        # 품질 검증
        quality = self.quality_checker.check(extraction, page_count)
        logger.info(
            "Quality check: passed=%s, reason=%s, details=%s",
            quality.passed, quality.reason, quality.details,
        )

        if quality.passed:
            return extraction

        # 2단계: 재처리 필요
        logger.info(
            "Step 2: Reprocessing with mode=%s (reason: %s)",
            quality.recommended_mode, quality.reason,
        )

        if quality.recommended_mode == "ocr":
            extraction = self.pdf_service.extract(
                file_path=file_obj.storage_path,
                ocr_enabled=True,
                use_hybrid=True,
            )
        elif quality.recommended_mode == "accurate":
            extraction = self.pdf_service.extract(
                file_path=file_obj.storage_path,
                ocr_enabled=False,
                use_hybrid=True,
            )

        # 재처리 기록
        job.auto_reprocessed = True
        job.reprocess_reason = quality.reason

        return extraction

    async def _save_results_and_chunks(
        self,
        extraction: dict,
        job: Job,
        result_repo: ResultRepository,
        chunk_repo: ChunkRepository,
    ) -> None:
        """추출 결과를 정규화하여 저장하고 청킹 처리."""

        # 정규화
        normalized_text = self.normalizer.normalize(extraction["text"])
        normalized_markdown = self.normalizer.normalize(extraction["markdown"])

        # 결과 저장
        result = Result(
            job_id=job.id,
            file_id=job.file_id,
            content_text=normalized_text,
            content_markdown=normalized_markdown,
            content_json=extraction.get("json_raw", extraction["json"]),
        )
        result = await result_repo.create(result)

        # 청킹
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

        # 청크 저장 (정규화 적용)
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
