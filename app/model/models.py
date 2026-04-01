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
    use_hybrid = Column(Boolean, default=False, nullable=False)
    auto_reprocessed = Column(Boolean, default=False, nullable=False)
    reprocess_reason = Column(String(50), nullable=True)
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
