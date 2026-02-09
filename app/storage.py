import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


class StorageService:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file: UploadFile) -> tuple[str, int]:
        """Save an uploaded file and return (file_path, file_size)."""
        ext = Path(file.filename or "document.pdf").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File extension '{ext}' is not allowed")

        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = (self.upload_dir / unique_name).resolve()

        # Ensure the resolved path stays inside upload_dir (prevent traversal)
        if not str(file_path).startswith(str(self.upload_dir)):
            raise ValueError("Invalid file path")

        max_bytes = settings.max_file_size_mb * 1024 * 1024
        chunks = []
        total = 0
        while True:
            chunk = await file.read(64 * 1024)  # 64KB chunks
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(
                    f"File size exceeds {settings.max_file_size_mb}MB limit"
                )
            chunks.append(chunk)

        content = b"".join(chunks)
        file_path.write_bytes(content)
        return str(file_path), total

    def delete_file(self, file_path: str) -> None:
        """Remove a file from disk."""
        path = Path(file_path)
        if path.exists():
            path.unlink()


storage_service = StorageService()
