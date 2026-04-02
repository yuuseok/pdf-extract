import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings


class FileService:
    ALLOWED_EXTENSIONS = {".pdf", ".hwp", ".hwpx"}
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/x-hwp",
        "application/haansofthwp",
        "application/vnd.hancom.hwpx",
        "application/x-hwpx+zip",
        "application/octet-stream",  # 브라우저가 HWP/HWPX MIME을 모를 경우 fallback
    }

    def validate_file(self, file: UploadFile) -> None:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_FILE_TYPE",
                    "message": f"지원하지 않는 파일 형식입니다. 허용: {allowed}",
                },
            )

        # 확장자가 유효하면 MIME 타입도 확인 (HWP/HWPX는 octet-stream으로 올 수 있음)
        if file.content_type not in self.ALLOWED_MIME_TYPES:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_FILE_TYPE",
                    "message": f"지원하지 않는 파일 형식입니다. 허용: {allowed}",
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
