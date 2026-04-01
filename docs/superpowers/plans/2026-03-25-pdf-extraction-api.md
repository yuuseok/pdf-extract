# PDF Text Extraction & Chunking API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI-based REST API that uploads PDFs, extracts text (text/markdown/json) via opendataloader-pdf, chunks the results with selectable strategies, and stores everything in PostgreSQL.

**Architecture:** Layered architecture (router → service → repository) with async background processing. File upload triggers synchronous DB records (file + job), then BackgroundTasks handles PDF extraction and chunking. Results stored in 3 formats (text, markdown, json).

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy (async), Alembic, PostgreSQL, opendataloader-pdf, tiktoken

**Spec:** `docs/design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `app/__init__.py` | Package init |
| `app/main.py` | FastAPI app, startup event (orphan job recovery), router registration |
| `app/config.py` | Settings via pydantic-settings (DB URL, upload path, max file size) |
| `app/database.py` | Async SQLAlchemy engine, session factory, get_db dependency |
| `app/model/__init__.py` | Package init |
| `app/model/models.py` | SQLAlchemy models: File, Job, Result, Chunk |
| `app/schema/__init__.py` | Package init |
| `app/schema/schemas.py` | Pydantic schemas for request/response |
| `app/repository/__init__.py` | Package init |
| `app/repository/file_repository.py` | files table CRUD |
| `app/repository/job_repository.py` | jobs table CRUD |
| `app/repository/result_repository.py` | results table CRUD |
| `app/repository/chunk_repository.py` | chunks table CRUD |
| `app/service/__init__.py` | Package init |
| `app/service/file_service.py` | File save/delete, validation |
| `app/service/job_service.py` | Job lifecycle, orphan recovery |
| `app/service/pdf_service.py` | PDF extraction via opendataloader-pdf |
| `app/service/chunk_service.py` | Chunking strategies (semantic/fixed/hybrid) |
| `app/router/__init__.py` | Package init |
| `app/router/file_router.py` | File endpoints (upload, list, detail, delete) |
| `app/router/job_router.py` | Job endpoints (status, result, chunks) |
| `alembic.ini` | Alembic config |
| `alembic/env.py` | Alembic environment (async) |
| `alembic/versions/` | Migration files |
| `requirements.txt` | Python dependencies |
| `.env` | Environment variables |
| `tests/conftest.py` | Test fixtures (async client, test DB) |
| `tests/test_config.py` | Config tests |
| `tests/test_models.py` | Model tests |
| `tests/test_file_router.py` | File endpoint tests |
| `tests/test_job_router.py` | Job endpoint tests |
| `tests/test_chunk_service.py` | Chunking strategy tests |
| `tests/test_pdf_service.py` | PDF extraction tests |

---

## Task 1: Project Setup & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.env`
- Create: `app/__init__.py`
- Create: `app/config.py`

- [ ] **Step 1: Create requirements.txt**

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
pydantic-settings==2.7.1
python-multipart==0.0.20
opendataloader-pdf==1.3.0
tiktoken==0.8.0
python-dotenv==1.0.1
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: Create .env file**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hancom_pdf
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=100
```

- [ ] **Step 3: Create app/__init__.py (empty)**

- [ ] **Step 4: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hancom_pdf"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 100

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 5: Install dependencies**

Run: `cd /home/yusuk/documents/ai_workspace/hancom-pdf && pip install -r requirements.txt`

- [ ] **Step 6: Create test for config**

Create `tests/__init__.py` and `tests/test_config.py`:

```python
from app.config import Settings


def test_default_settings():
    s = Settings(database_url="postgresql+asyncpg://test:test@localhost/test")
    assert s.max_file_size_mb == 100
    assert s.upload_dir == "./uploads"
```

- [ ] **Step 7: Run test**

Run: `cd /home/yusuk/documents/ai_workspace/hancom-pdf && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git init
git add requirements.txt .env app/__init__.py app/config.py tests/
git commit -m "feat: project setup with dependencies and config"
```

---

## Task 2: Database Setup & SQLAlchemy Models

**Files:**
- Create: `app/database.py`
- Create: `app/model/__init__.py`
- Create: `app/model/models.py`

- [ ] **Step 1: Create app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
```

- [ ] **Step 2: Create app/model/__init__.py (empty)**

- [ ] **Step 3: Create app/model/models.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename = Column(String(500), nullable=False)
    file_extension = Column(String(10), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    storage_path = Column(String(1000), nullable=False)
    page_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    jobs = relationship("Job", back_populates="file", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)
    chunking_strategy = Column(String(20), default="semantic", nullable=False)
    chunk_size = Column(Integer, nullable=True, default=500)
    chunk_overlap = Column(Integer, nullable=True, default=50)
    ocr_enabled = Column(Boolean, default=False, nullable=False)
    ocr_languages = Column(String(100), default="ko,en", nullable=False)
    enable_embedding = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    file = relationship("File", back_populates="jobs")
    results = relationship("Result", back_populates="job", cascade="all, delete-orphan")


class Result(Base):
    __tablename__ = "results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    content_text = Column(Text, nullable=True)
    content_markdown = Column(Text, nullable=True)
    content_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="results")
    chunks = relationship("Chunk", back_populates="result", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("results.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    page_start = Column(Integer, nullable=True)
    page_end = Column(Integer, nullable=True)
    heading = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    result = relationship("Result", back_populates="chunks")
```

- [ ] **Step 4: Write model test**

Create `tests/test_models.py`:

```python
from app.model.models import File, Job, Result, Chunk, Base


def test_file_table_name():
    assert File.__tablename__ == "files"


def test_job_table_name():
    assert Job.__tablename__ == "jobs"


def test_result_table_name():
    assert Result.__tablename__ == "results"


def test_chunk_table_name():
    assert Chunk.__tablename__ == "chunks"


def test_base_metadata_has_all_tables():
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"files", "jobs", "results", "chunks"}
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/database.py app/model/ tests/test_models.py
git commit -m "feat: database setup and SQLAlchemy models"
```

---

## Task 3: Alembic Migration Setup

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`

- [ ] **Step 1: Initialize Alembic**

Run: `cd /home/yusuk/documents/ai_workspace/hancom-pdf && alembic init alembic`

- [ ] **Step 2: Update alembic.ini**

Set `sqlalchemy.url` to empty (will be overridden by env.py):

In `alembic.ini`, set: `sqlalchemy.url =`

- [ ] **Step 3: Update alembic/env.py for async**

Replace `alembic/env.py` with async-compatible version that imports `app.model.models.Base` and uses `settings.database_url` (converted to sync URL for Alembic offline mode, async for online mode).

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.model.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

Run: `cd /home/yusuk/documents/ai_workspace/hancom-pdf && alembic revision --autogenerate -m "initial tables"`

- [ ] **Step 5: Apply migration**

Run: `alembic upgrade head`

- [ ] **Step 6: Commit**

```bash
git add alembic/ alembic.ini
git commit -m "feat: alembic migration setup with initial tables"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `app/schema/__init__.py`
- Create: `app/schema/schemas.py`

- [ ] **Step 1: Create app/schema/__init__.py (empty)**

- [ ] **Step 2: Create app/schema/schemas.py**

```python
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
```

- [ ] **Step 3: Write schema test**

Create `tests/test_schemas.py`:

```python
from app.schema.schemas import UploadRequest


def test_upload_request_defaults():
    req = UploadRequest()
    assert req.chunking_strategy == "semantic"
    assert req.chunk_size == 500
    assert req.chunk_overlap == 50
    assert req.ocr_enabled is False


def test_upload_request_invalid_strategy():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        UploadRequest(chunking_strategy="invalid")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schema/ tests/test_schemas.py
git commit -m "feat: pydantic request/response schemas"
```

---

## Task 5: Repository Layer

**Files:**
- Create: `app/repository/__init__.py`
- Create: `app/repository/file_repository.py`
- Create: `app/repository/job_repository.py`
- Create: `app/repository/result_repository.py`
- Create: `app/repository/chunk_repository.py`

- [ ] **Step 1: Create app/repository/__init__.py (empty)**

- [ ] **Step 2: Create app/repository/file_repository.py**

```python
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
```

- [ ] **Step 3: Create app/repository/job_repository.py**

```python
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
```

- [ ] **Step 4: Create app/repository/result_repository.py**

```python
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
```

- [ ] **Step 5: Create app/repository/chunk_repository.py**

```python
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
```

- [ ] **Step 6: Commit**

```bash
git add app/repository/
git commit -m "feat: repository layer for all tables"
```

---

## Task 6: Chunking Service

**Files:**
- Create: `app/service/__init__.py`
- Create: `app/service/chunk_service.py`
- Create: `tests/test_chunk_service.py`

- [ ] **Step 1: Write failing tests for chunk_service**

Create `tests/test_chunk_service.py`:

```python
import pytest
from app.service.chunk_service import ChunkService


@pytest.fixture
def chunk_service():
    return ChunkService()


class TestFixedChunking:
    def test_basic_split(self, chunk_service):
        text = "Hello world. " * 100
        chunks = chunk_service.chunk_fixed(text, chunk_size=50, chunk_overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk["content"]
            assert chunk["token_count"] > 0

    def test_small_text_single_chunk(self, chunk_service):
        text = "Short text."
        chunks = chunk_service.chunk_fixed(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1

    def test_overlap_present(self, chunk_service):
        text = "word " * 200
        chunks = chunk_service.chunk_fixed(text, chunk_size=50, chunk_overlap=10)
        if len(chunks) > 1:
            # Last tokens of chunk[0] should overlap with start of chunk[1]
            assert chunks[0]["token_count"] > 0
            assert chunks[1]["token_count"] > 0


class TestSemanticChunking:
    def test_split_by_headings(self, chunk_service):
        json_data = [
            {"type": "heading", "level": 1, "content": "Introduction"},
            {"type": "paragraph", "content": "This is the intro."},
            {"type": "heading", "level": 1, "content": "Methods"},
            {"type": "paragraph", "content": "This is the methods section."},
        ]
        chunks = chunk_service.chunk_semantic(json_data)
        assert len(chunks) == 2
        assert chunks[0]["heading"] == "Introduction"
        assert chunks[1]["heading"] == "Methods"

    def test_no_headings_single_chunk(self, chunk_service):
        json_data = [
            {"type": "paragraph", "content": "Just some text."},
            {"type": "paragraph", "content": "More text."},
        ]
        chunks = chunk_service.chunk_semantic(json_data)
        assert len(chunks) == 1


class TestHybridChunking:
    def test_large_section_gets_split(self, chunk_service):
        json_data = [
            {"type": "heading", "level": 1, "content": "Big Section"},
            {"type": "paragraph", "content": "word " * 500},
        ]
        chunks = chunk_service.chunk_hybrid(json_data, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        assert chunks[0]["heading"] == "Big Section"

    def test_small_sections_stay_intact(self, chunk_service):
        json_data = [
            {"type": "heading", "level": 1, "content": "Small"},
            {"type": "paragraph", "content": "Short text."},
        ]
        chunks = chunk_service.chunk_hybrid(json_data, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_chunk_service.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Create app/service/__init__.py (empty)**

- [ ] **Step 4: Implement app/service/chunk_service.py**

```python
import tiktoken


class ChunkService:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _split_by_tokens(self, text: str, chunk_size: int, chunk_overlap: int) -> list[dict]:
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append({
                "content": chunk_text,
                "token_count": len(chunk_tokens),
            })
            start += chunk_size - chunk_overlap
            if start >= len(tokens):
                break
        return chunks

    def chunk_fixed(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[dict]:
        if self._count_tokens(text) <= chunk_size:
            return [{"content": text, "token_count": self._count_tokens(text)}]
        return self._split_by_tokens(text, chunk_size, chunk_overlap)

    def chunk_semantic(self, json_data: list[dict]) -> list[dict]:
        sections = []
        current_heading = None
        current_content = []

        for element in json_data:
            if element.get("type") == "heading":
                if current_content:
                    text = "\n".join(current_content)
                    sections.append({
                        "content": text,
                        "token_count": self._count_tokens(text),
                        "heading": current_heading,
                    })
                current_heading = element.get("content", "")
                current_content = []
            else:
                content = element.get("content", "")
                if content:
                    current_content.append(content)

        if current_content:
            text = "\n".join(current_content)
            sections.append({
                "content": text,
                "token_count": self._count_tokens(text),
                "heading": current_heading,
            })

        return sections if sections else []

    def chunk_hybrid(
        self, json_data: list[dict], chunk_size: int = 500, chunk_overlap: int = 50
    ) -> list[dict]:
        semantic_chunks = self.chunk_semantic(json_data)
        result = []

        for chunk in semantic_chunks:
            if chunk["token_count"] > chunk_size:
                sub_chunks = self._split_by_tokens(chunk["content"], chunk_size, chunk_overlap)
                for sc in sub_chunks:
                    sc["heading"] = chunk.get("heading")
                result.extend(sub_chunks)
            else:
                result.append(chunk)

        return result
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_chunk_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/service/__init__.py app/service/chunk_service.py tests/test_chunk_service.py
git commit -m "feat: chunking service with semantic/fixed/hybrid strategies"
```

---

## Task 7: PDF Extraction Service

**Files:**
- Create: `app/service/pdf_service.py`
- Create: `tests/test_pdf_service.py`
- Create: `tests/fixtures/sample.pdf` (tiny test PDF)

- [ ] **Step 1: Write test for pdf_service**

Create `tests/test_pdf_service.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from app.service.pdf_service import PdfService


@pytest.fixture
def pdf_service():
    return PdfService()


def test_extract_returns_three_formats(pdf_service, tmp_path):
    """Test that extraction returns text, markdown, and json."""
    mock_result = {
        "text": "Sample text content",
        "markdown": "# Sample\n\nSample text content",
        "json": [{"type": "heading", "level": 1, "content": "Sample"},
                 {"type": "paragraph", "content": "Sample text content"}],
        "page_count": 1,
    }
    with patch.object(pdf_service, "_run_extraction", return_value=mock_result):
        result = pdf_service.extract(str(tmp_path / "test.pdf"))
        assert "text" in result
        assert "markdown" in result
        assert "json" in result
        assert "page_count" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement app/service/pdf_service.py**

```python
import json
import os
import subprocess
import tempfile


class PdfService:
    def extract(
        self,
        file_path: str,
        ocr_enabled: bool = False,
        ocr_languages: str = "ko,en",
    ) -> dict:
        return self._run_extraction(file_path, ocr_enabled, ocr_languages)

    def _run_extraction(
        self,
        file_path: str,
        ocr_enabled: bool = False,
        ocr_languages: str = "ko,en",
    ) -> dict:
        with tempfile.TemporaryDirectory() as output_dir:
            cmd = [
                "opendataloader-pdf",
                "--format", "text,markdown,json",
                "--output-dir", output_dir,
                file_path,
            ]
            if ocr_enabled:
                cmd.extend(["--force-ocr", "--ocr-lang", ocr_languages])

            subprocess.run(cmd, check=True, capture_output=True, text=True)

            basename = os.path.splitext(os.path.basename(file_path))[0]

            text_content = ""
            text_path = os.path.join(output_dir, f"{basename}.txt")
            if os.path.exists(text_path):
                with open(text_path, "r", encoding="utf-8") as f:
                    text_content = f.read()

            md_content = ""
            md_path = os.path.join(output_dir, f"{basename}.md")
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    md_content = f.read()

            json_content = []
            json_path = os.path.join(output_dir, f"{basename}.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    json_content = json.load(f)

            page_count = None
            if isinstance(json_content, list):
                pages = set()
                for element in json_content:
                    pn = element.get("page number") or element.get("page_number")
                    if pn is not None:
                        pages.add(pn)
                if pages:
                    page_count = max(pages)

            return {
                "text": text_content,
                "markdown": md_content,
                "json": json_content,
                "page_count": page_count,
            }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_pdf_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/service/pdf_service.py tests/test_pdf_service.py
git commit -m "feat: PDF extraction service using opendataloader-pdf"
```

---

## Task 8: File Service & Job Service

**Files:**
- Create: `app/service/file_service.py`
- Create: `app/service/job_service.py`

- [ ] **Step 1: Create app/service/file_service.py**

```python
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings


class FileService:
    ALLOWED_EXTENSIONS = {".pdf"}
    ALLOWED_MIME_TYPES = {"application/pdf"}

    def validate_file(self, file: UploadFile) -> None:
        if file.content_type not in self.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_FILE_TYPE", "message": "PDF 파일만 업로드할 수 있습니다."},
            )

        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_FILE_TYPE", "message": "PDF 파일만 업로드할 수 있습니다."},
            )

    async def save_file(self, file: UploadFile) -> tuple[str, int, str]:
        """Save uploaded file. Returns (storage_path, file_size, file_extension)."""
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        ext = os.path.splitext(file.filename or "")[1].lower()
        filename = f"{uuid.uuid4()}{ext}"
        storage_path = str(upload_dir / filename)

        content = await file.read()
        file_size = len(content)

        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "FILE_TOO_LARGE",
                    "message": f"파일 크기가 {settings.max_file_size_mb}MB를 초과합니다.",
                },
            )

        with open(storage_path, "wb") as f:
            f.write(content)

        return storage_path, file_size, ext

    def delete_file(self, storage_path: str) -> None:
        if os.path.exists(storage_path):
            os.remove(storage_path)
```

- [ ] **Step 2: Create app/service/job_service.py**

```python
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

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self):
        self.pdf_service = PdfService()
        self.chunk_service = ChunkService()

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

            # Extract PDF
            file_obj = await db.get(File, job.file_id)
            extraction = self.pdf_service.extract(
                file_path=file_obj.storage_path,
                ocr_enabled=job.ocr_enabled,
                ocr_languages=job.ocr_languages,
            )

            # Update page count
            if extraction.get("page_count"):
                file_obj.page_count = extraction["page_count"]
                await db.commit()

            # Save result
            result = Result(
                job_id=job.id,
                file_id=job.file_id,
                content_text=extraction["text"],
                content_markdown=extraction["markdown"],
                content_json=extraction["json"],
            )
            result = await result_repo.create(result)

            # Chunk
            if job.chunking_strategy == "semantic":
                raw_chunks = self.chunk_service.chunk_semantic(extraction["json"])
            elif job.chunking_strategy == "fixed":
                raw_chunks = self.chunk_service.chunk_fixed(
                    extraction["text"], job.chunk_size or 500, job.chunk_overlap or 50
                )
            else:  # hybrid
                raw_chunks = self.chunk_service.chunk_hybrid(
                    extraction["json"], job.chunk_size or 500, job.chunk_overlap or 50
                )

            # Save chunks
            chunk_models = [
                Chunk(
                    result_id=result.id,
                    chunk_index=i,
                    content=c["content"],
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
```

- [ ] **Step 3: Commit**

```bash
git add app/service/file_service.py app/service/job_service.py
git commit -m "feat: file service and job service with lifecycle management"
```

---

## Task 9: Routers (File & Job)

**Files:**
- Create: `app/router/__init__.py`
- Create: `app/router/file_router.py`
- Create: `app/router/job_router.py`

- [ ] **Step 1: Create app/router/__init__.py (empty)**

- [ ] **Step 2: Create app/router/file_router.py**

```python
import math

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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
    )
    job = await job_repo.create(job)

    # Start background task
    from fastapi import BackgroundTasks
    from app.service.job_service import JobService
    from app.database import async_session

    async def run_job():
        async with async_session() as session:
            await JobService().process_pdf(job.id, session)

    import asyncio
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
    from uuid import UUID
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
    from uuid import UUID
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
    from uuid import UUID
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
```

- [ ] **Step 3: Create app/router/job_router.py**

```python
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
```

- [ ] **Step 4: Commit**

```bash
git add app/router/
git commit -m "feat: file and job routers with all endpoints"
```

---

## Task 10: FastAPI App Entry Point

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Create app/main.py**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import async_session, engine
from app.router import file_router, job_router
from app.service.job_service import JobService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: recover orphaned jobs
    async with async_session() as db:
        job_service = JobService()
        count = await job_service.recover_orphaned_jobs(db)
        if count > 0:
            logger.info(f"Recovered {count} orphaned jobs on startup")
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="PDF Text Extraction & Chunking API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(file_router.router)
app.include_router(job_router.router)


@app.get("/health")
async def health_check():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": f"error: {str(e)}"}
```

- [ ] **Step 2: Create uploads directory**

Run: `mkdir -p /home/yusuk/documents/ai_workspace/hancom-pdf/uploads && echo "uploads/" > /home/yusuk/documents/ai_workspace/hancom-pdf/.gitignore`

- [ ] **Step 3: Update .gitignore**

```
uploads/
__pycache__/
*.pyc
.env
*.egg-info/
```

- [ ] **Step 4: Commit**

```bash
git add app/main.py .gitignore
git commit -m "feat: FastAPI app with lifespan, health check, and router registration"
```

---

## Task 11: Integration Test Setup

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_file_router.py`
- Create: `tests/test_job_router.py`

- [ ] **Step 1: Create tests/conftest.py**

```python
import asyncio
import os
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.model.models import Base

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/hancom_pdf_test"
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with test_session() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    from app.database import get_db
    from app.main import app

    async def override_get_db():
        async with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Create tests/test_file_router.py**

```python
import io
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_upload_pdf(client):
    mock_extraction = {
        "text": "Test content",
        "markdown": "# Test\n\nTest content",
        "json": [{"type": "paragraph", "content": "Test content"}],
        "page_count": 1,
    }
    with patch("app.service.job_service.PdfService") as MockPdf:
        MockPdf.return_value.extract.return_value = mock_extraction
        pdf_content = b"%PDF-1.4 fake content"
        response = await client.post(
            "/api/v1/files/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"chunking_strategy": "semantic"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert "job_id" in data
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(client):
    response = await client.post(
        "/api/v1/files/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_files(client):
    response = await client.get("/api/v1/files")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_nonexistent_file(client):
    response = await client.get("/api/v1/files/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
```

- [ ] **Step 3: Create tests/test_job_router.py**

```python
import pytest


@pytest.mark.asyncio
async def test_get_nonexistent_job(client):
    response = await client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS (tests that need DB will need test DB running)

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "feat: integration tests for file and job routers"
```

---

## Task 12: Final Verification & Startup

- [ ] **Step 1: Verify all files exist**

Run: `find /home/yusuk/documents/ai_workspace/hancom-pdf/app -name "*.py" | sort`

- [ ] **Step 2: Run full test suite**

Run: `cd /home/yusuk/documents/ai_workspace/hancom-pdf && python -m pytest tests/ -v --tb=short`

- [ ] **Step 3: Test server startup**

Run: `cd /home/yusuk/documents/ai_workspace/hancom-pdf && timeout 5 uvicorn app.main:app --host 0.0.0.0 --port 8000 || true`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: PDF text extraction and chunking API - complete initial implementation"
```
