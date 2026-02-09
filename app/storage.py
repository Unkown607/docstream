import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


class StorageService:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file: UploadFile) -> tuple[str, int]:
        """Save an uploaded file and return (file_path, file_size)."""
        ext = Path(file.filename or "document").suffix
        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = self.upload_dir / unique_name

        content = await file.read()
        file_size = len(content)

        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds "
                f"{settings.max_file_size_mb}MB limit"
            )

        file_path.write_bytes(content)
        return str(file_path), file_size

    def delete_file(self, file_path: str) -> None:
        """Remove a file from disk."""
        path = Path(file_path)
        if path.exists():
            path.unlink()


storage_service = StorageService()
