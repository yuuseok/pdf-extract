import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings


class FileService:
    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".docx",
        ".xlsx", ".xls",
        ".pptx",
        ".csv", ".tsv",
        ".hwp", ".hwpx",
    }

    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # .xlsx
        "application/vnd.ms-excel",                                                 # .xls
        "application/vnd.openxmlformats-officedocument.presentationml.presentation", # .pptx
        "text/csv",                                                                 # .csv
        "text/tab-separated-values",                                                # .tsv
        "application/x-hwp",                                                        # .hwp
        "application/haansofthwp",                                                  # .hwp
        "application/vnd.hancom.hwpx",                                              # .hwpx
        "application/x-hwpx+zip",                                                   # .hwpx
        "application/octet-stream",  # 일부 클라이언트가 보내는 범용 타입
    }

    SUPPORTED_FORMATS_MSG = "지원 형식: PDF, Word(.docx), Excel(.xlsx), PowerPoint(.pptx), CSV/TSV, HWP/HWPX"

    def validate_file(self, file: UploadFile) -> None:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_FILE_TYPE",
                    "message": f"지원하지 않는 파일 형식입니다. {self.SUPPORTED_FORMATS_MSG}",
                },
            )

        # MIME 타입 검증 (확장자 우선, MIME은 보조 — 일부 클라이언트가 부정확하게 보냄)
        if file.content_type and file.content_type not in self.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_FILE_TYPE",
                    "message": f"지원하지 않는 파일 형식입니다. {self.SUPPORTED_FORMATS_MSG}",
                },
            )

    async def save_file(self, file: UploadFile) -> tuple[str, int, str]:
        """Save uploaded file. Returns (storage_path, file_size, file_extension)."""
        upload_dir = Path(settings.upload_dir).resolve()
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
