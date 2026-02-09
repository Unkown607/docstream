import asyncio
import base64
import json
import logging

import fitz  # PyMuPDF
from anthropic import AsyncAnthropic

from app.config import settings
from app.schemas import ExtractionResult, LineItem

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Je bent een expert document-extractor gespecialiseerd in Nederlandse en Europese facturen en bonnen.

Analyseer dit document en extraheer de volgende informatie als valide JSON:

{
    "vendor_name": "Naam van de leverancier/bedrijf",
    "invoice_number": "Factuurnummer",
    "invoice_date": "YYYY-MM-DD",
    "due_date": "YYYY-MM-DD",
    "total_amount": 0.00,
    "vat_amount": 0.00,
    "vat_percentage": 21.0,
    "currency": "EUR",
    "iban": "NL00BANK0000000000",
    "line_items": [
        {
            "description": "Omschrijving",
            "quantity": 1.0,
            "unit_price": 0.00,
            "total": 0.00,
            "vat_percentage": 21.0
        }
    ],
    "confidence": 0.95
}

Regels:
- Retourneer UITSLUITEND valide JSON. Geen tekst ervoor of erna.
- Gebruik null voor velden die niet te vinden zijn in het document.
- Bedragen zijn numeriek zonder valutasymbolen.
- Datums in YYYY-MM-DD formaat.
- total_amount is het eindbedrag INCLUSIEF BTW.
- vat_amount is het BTW-bedrag apart.
- Als het document geen factuur of bon is, zet alle velden op null en confidence op 0.0.
- confidence geeft aan hoe zeker je bent over de gehele extractie (0.0 tot 1.0)."""


class ExtractionService:
    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        """Extract structured invoice data from a document using Claude Vision."""
        images = await self._prepare_images(file_path, mime_type)

        content: list[dict] = []
        for img_b64, img_media_type in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img_media_type,
                        "data": img_b64,
                    },
                }
            )
        content.append({"type": "text", "text": EXTRACTION_PROMPT})

        response = await self.client.messages.create(
            model=settings.extraction_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        return self._parse_response(response)

    async def _prepare_images(
        self, file_path: str, mime_type: str
    ) -> list[tuple[str, str]]:
        """Convert document to base64-encoded images for the Vision API."""
        if mime_type == "application/pdf":
            return await asyncio.to_thread(self._pdf_to_images, file_path)

        # Image files: read directly
        with open(file_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
        return [(b64, mime_type)]

    @staticmethod
    def _pdf_to_images(file_path: str, max_pages: int = 5) -> list[tuple[str, str]]:
        """Convert PDF pages to base64 PNG images using PyMuPDF."""
        doc = fitz.open(file_path)
        result = []
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            # Render at 2x zoom for good quality
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            png_bytes = pix.tobytes("png")
            b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
            result.append((b64, "image/png"))
        doc.close()
        return result

    def _parse_response(self, response) -> ExtractionResult:
        """Parse the LLM response into a structured ExtractionResult."""
        raw_text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            raw_text = raw_text.rsplit("```", 1)[0].strip()

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse extraction response: %s", raw_text[:500])
            return ExtractionResult(confidence=0.0)

        line_items = []
        for item in data.get("line_items") or []:
            if isinstance(item, dict):
                line_items.append(LineItem(**item))

        return ExtractionResult(
            vendor_name=data.get("vendor_name"),
            invoice_number=data.get("invoice_number"),
            invoice_date=data.get("invoice_date"),
            due_date=data.get("due_date"),
            total_amount=data.get("total_amount"),
            vat_amount=data.get("vat_amount"),
            vat_percentage=data.get("vat_percentage"),
            currency=data.get("currency", "EUR"),
            iban=data.get("iban"),
            line_items=line_items,
            confidence=data.get("confidence", 0.0),
        )


extraction_service = ExtractionService()
