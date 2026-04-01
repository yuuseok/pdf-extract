import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repository.chunk_repository import ChunkRepository
from app.repository.job_repository import JobRepository
from app.repository.result_repository import ResultRepository
from app.schema.schemas import ChunkResponse, JobResponse, PaginatedResponse, ResultResponse

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    repo = JobRepository(db)
    job = await repo.get_by_id(UUID(job_id))
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "작업을 찾을 수 없습니다."},
        )
    return JobResponse.model_validate(job)


@router.get("/{job_id}/result", response_model=ResultResponse)
async def get_job_result(job_id: str, db: AsyncSession = Depends(get_db)):
    job_repo = JobRepository(db)
    job = await job_repo.get_by_id(UUID(job_id))
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "작업을 찾을 수 없습니다."},
        )

    result_repo = ResultRepository(db)
    result = await result_repo.get_by_job_id(UUID(job_id))
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESULT_NOT_FOUND", "message": "결과가 아직 생성되지 않았습니다."},
        )
    return ResultResponse.model_validate(result)


@router.get("/{job_id}/chunks", response_model=PaginatedResponse)
async def get_job_chunks(
    job_id: str,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
):
    per_page = min(per_page, 100)

    job_repo = JobRepository(db)
    job = await job_repo.get_by_id(UUID(job_id))
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "작업을 찾을 수 없습니다."},
        )

    result_repo = ResultRepository(db)
    result = await result_repo.get_by_job_id(UUID(job_id))
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESULT_NOT_FOUND", "message": "결과가 아직 생성되지 않았습니다."},
        )

    chunk_repo = ChunkRepository(db)
    chunks, total = await chunk_repo.get_by_result_id(result.id, page, per_page)
    return PaginatedResponse(
        items=[ChunkResponse.model_validate(c) for c in chunks],
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page) if per_page > 0 else 0,
    )
