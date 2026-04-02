import asyncio
import logging

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.database import async_session
from app.model.models import File as FileModel
from app.model.models import Job
from app.repository.file_repository import FileRepository
from app.repository.job_repository import JobRepository
from app.schema.schemas import FileResponse, JobResponse, UploadResponse
from app.service.file_service import FileService
from app.service.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    chunking_strategy: str = Form(default="semantic"),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=50),
    ocr_enabled: bool = Form(default=False),
    ocr_languages: str = Form(default="ko,en"),
    enable_embedding: bool = Form(default=False),
    use_hybrid: bool = Form(default=False),
):
    file_service = FileService()
    file_service.validate_file(file)

    async with async_session() as db:
        file_repo = FileRepository(db)
        job_repo = JobRepository(db)

        storage_path, file_size, ext = await file_service.save_file(file)

        file_obj = FileModel(
            original_filename=file.filename,
            storage_path=storage_path,
            file_size=file_size,
            file_extension=ext,
        )
        file_obj = await file_repo.create(file_obj)

        job = Job(
            file_id=file_obj.id,
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            ocr_enabled=ocr_enabled,
            ocr_languages=ocr_languages,
            enable_embedding=enable_embedding,
            use_hybrid=use_hybrid,
        )
        job = await job_repo.create(job)

    # Start background task with a fresh DB session
    async def run_job():
        async with async_session() as session:
            await JobService().process_file(job.id, session)

    asyncio.get_event_loop().create_task(run_job())

    return UploadResponse(
        file_id=file_obj.id,
        job_id=job.id,
        status="PENDING",
        message="파일 업로드 완료. 비동기 처리가 시작되었습니다.",
    )


@router.get("", response_model=dict)
async def list_files(page: int = 1, per_page: int = 20):
    async with async_session() as db:
        file_repo = FileRepository(db)
        files, total = await file_repo.get_all(page=page, per_page=per_page)
        return {
            "items": [FileResponse.model_validate(f) for f in files],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: str):
    from uuid import UUID

    async with async_session() as db:
        file_repo = FileRepository(db)
        file_obj = await file_repo.get_by_id(UUID(file_id))
        if not file_obj:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse.model_validate(file_obj)


@router.get("/{file_id}/jobs", response_model=list[JobResponse])
async def get_file_jobs(file_id: str):
    from uuid import UUID

    async with async_session() as db:
        job_repo = JobRepository(db)
        jobs = await job_repo.get_by_file_id(UUID(file_id))
        return [JobResponse.model_validate(j) for j in jobs]


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    from uuid import UUID

    file_service = FileService()
    async with async_session() as db:
        file_repo = FileRepository(db)
        file_obj = await file_repo.get_by_id(UUID(file_id))
        if not file_obj:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="File not found")

        file_service.delete_file(file_obj.storage_path)
        await file_repo.delete(file_obj)
        return {"message": "파일이 삭제되었습니다."}
