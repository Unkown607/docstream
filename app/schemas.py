from datetime import datetime

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    total: float | None = None
    vat_percentage: float | None = None


class ExtractionResult(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    total_amount: float | None = None
    vat_amount: float | None = None
    vat_percentage: float | None = None
    currency: str = "EUR"
    iban: str | None = None
    line_items: list[LineItem] = []
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    extraction: ExtractionResult | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
