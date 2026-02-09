import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.extraction import extraction_service
from app.models import Document, DocumentStatus
from app.schemas import DocumentListResponse, DocumentResponse, ExtractionResult
from app.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}


@router.post("/upload", response_model=DocumentResponse)
async def upload_and_extract(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload a document (PDF/image) and extract invoice data."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {file.content_type}. "
                f"Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            ),
        )

    # Save file to disk
    try:
        file_path, file_size = await storage_service.save_file(file)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))

    # Create document record
    doc = Document(
        filename=file.filename or "unknown",
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Run extraction
    try:
        result = await extraction_service.extract(file_path, file.content_type)

        doc.vendor_name = result.vendor_name
        doc.invoice_number = result.invoice_number
        doc.invoice_date = result.invoice_date
        doc.due_date = result.due_date
        doc.total_amount = result.total_amount
        doc.vat_amount = result.vat_amount
        doc.vat_percentage = result.vat_percentage
        doc.currency = result.currency
        doc.iban = result.iban
        doc.line_items = [item.model_dump() for item in result.line_items]
        doc.raw_extraction = result.model_dump()
        doc.status = DocumentStatus.COMPLETED

        await db.commit()
        await db.refresh(doc)
        logger.info("Extraction completed for document %s", doc.id)

    except Exception:
        doc.status = DocumentStatus.FAILED
        await db.commit()
        logger.exception("Extraction failed for document %s", doc.id)
        raise HTTPException(
            status_code=500,
            detail="Document extraction failed. Check server logs for details.",
        )

    return _to_response(doc)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Retrieve a single document by ID."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List all documents, newest first."""
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    docs = result.scalars().all()

    count_result = await db.execute(select(func.count(Document.id)))
    total = count_result.scalar() or 0

    return DocumentListResponse(
        documents=[_to_response(d) for d in docs],
        total=total,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a document and its file."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_service.delete_file(doc.file_path)
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "id": document_id}


def _to_response(doc: Document) -> DocumentResponse:
    extraction = None
    if doc.raw_extraction:
        extraction = ExtractionResult(**doc.raw_extraction)

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value if isinstance(doc.status, DocumentStatus) else doc.status,
        extraction=extraction,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
