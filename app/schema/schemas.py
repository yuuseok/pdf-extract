from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Request ---

class UploadRequest(BaseModel):
    chunking_strategy: str = Field(default="semantic", pattern="^(semantic|fixed|hybrid)$")
    chunk_size: int = Field(default=500, ge=100, le=5000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)
    ocr_enabled: bool = False
    ocr_languages: str = "ko,en"
    enable_embedding: bool = False
    use_hybrid: bool = False


# --- Response ---

class UploadResponse(BaseModel):
    file_id: UUID
    job_id: UUID
    status: str
    message: str


class FileResponse(BaseModel):
    id: UUID
    original_filename: str
    file_extension: str
    file_size: int
    page_count: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: UUID
    file_id: UUID
    status: str
    chunking_strategy: str
    chunk_size: Optional[int]
    chunk_overlap: Optional[int]
    ocr_enabled: bool
    ocr_languages: str
    enable_embedding: bool
    use_hybrid: bool
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ResultResponse(BaseModel):
    id: UUID
    job_id: UUID
    file_id: UUID
    content_text: Optional[str]
    content_markdown: Optional[str]
    content_json: Optional[Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkResponse(BaseModel):
    id: UUID
    result_id: UUID
    chunk_index: int
    content: str
    token_count: int
    page_start: Optional[int]
    page_end: Optional[int]
    heading: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    database: str
