import asyncio
import math
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.model.models import File, Job
from app.repository.file_repository import FileRepository
from app.repository.job_repository import JobRepository
from app.schema.schemas import (
    FileResponse,
    JobResponse,
    PaginatedResponse,
    UploadResponse,
)
from app.service.file_service import FileService
from app.service.job_service import JobService

router = APIRouter(prefix="/api/v1/files", tags=["files"])
file_service = FileService()


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile,
    chunking_strategy: str = Form(default="semantic"),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=50),
    ocr_enabled: bool = Form(default=False),
    ocr_languages: str = Form(default="ko,en"),
    enable_embedding: bool = Form(default=False),
    use_hybrid: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
):
    file_service.validate_file(file)
    storage_path, file_size, ext = await file_service.save_file(file)

    file_repo = FileRepository(db)
    file_obj = File(
        original_filename=file.filename or "unknown.pdf",
        file_extension=ext,
        file_size=file_size,
        storage_path=storage_path,
    )
    file_obj = await file_repo.create(file_obj)

    job_repo = JobRepository(db)
    job = Job(
        file_id=file_obj.id,
        status="PENDING",
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


@router.get("", response_model=PaginatedResponse)
async def list_files(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
):
    per_page = min(per_page, 100)
    repo = FileRepository(db)
    files, total = await repo.get_list(page, per_page)
    return PaginatedResponse(
        items=[FileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if per_page > 0 else 0,
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: str, db: AsyncSession = Depends(get_db)):
    repo = FileRepository(db)
    file_obj = await repo.get_by_id(UUID(file_id))
    if not file_obj:
        raise HTTPException(
            status_code=404,
            detail={"code": "FILE_NOT_FOUND", "message": "파일을 찾을 수 없습니다."},
        )
    return FileResponse.model_validate(file_obj)


@router.get("/{file_id}/jobs", response_model=list[JobResponse])
async def get_file_jobs(file_id: str, db: AsyncSession = Depends(get_db)):
    file_repo = FileRepository(db)
    file_obj = await file_repo.get_by_id(UUID(file_id))
    if not file_obj:
        raise HTTPException(
            status_code=404,
            detail={"code": "FILE_NOT_FOUND", "message": "파일을 찾을 수 없습니다."},
        )
    job_repo = JobRepository(db)
    jobs = await job_repo.get_by_file_id(UUID(file_id))
    return [JobResponse.model_validate(j) for j in jobs]


@router.delete("/{file_id}", status_code=204)
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db)):
    file_repo = FileRepository(db)
    file_obj = await file_repo.get_by_id(UUID(file_id))
    if not file_obj:
        raise HTTPException(
            status_code=404,
            detail={"code": "FILE_NOT_FOUND", "message": "파일을 찾을 수 없습니다."},
        )

    job_repo = JobRepository(db)
    active_jobs = await job_repo.get_active_by_file_id(UUID(file_id))
    if active_jobs:
        raise HTTPException(
            status_code=409,
            detail={"code": "JOB_IN_PROGRESS", "message": "진행 중인 작업이 있어 삭제할 수 없습니다."},
        )

    file_service.delete_file(file_obj.storage_path)
    await file_repo.delete(file_obj)
