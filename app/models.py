import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus), default=DocumentStatus.PENDING
    )

    # Extracted data
    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String, nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    vat_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="EUR")
    iban: Mapped[str | None] = mapped_column(String, nullable=True)
    line_items: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
