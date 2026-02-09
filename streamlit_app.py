"""DocStream — AI Factuur Extractor voor ZZP'ers en MKB."""

import asyncio
import base64
import csv
import io
import json
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import streamlit as st
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DocStream — Factuur Extractor",
    page_icon="📄",
    layout="wide",
)

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

ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_api_key() -> str:
    """Retrieve API key from Streamlit secrets or .env file."""
    # Try streamlit secrets first (for Streamlit Cloud)
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass
    # Fall back to .env
    from dotenv import dotenv_values
    env = dotenv_values(".env")
    key = env.get("ANTHROPIC_API_KEY", "")
    if not key:
        st.error("Geen Anthropic API key gevonden. Maak een `.env` bestand aan of stel Streamlit Secrets in.")
        st.stop()
    return key


def file_to_images(file_bytes: bytes, mime_type: str) -> list[tuple[str, str]]:
    """Convert uploaded file to base64-encoded images."""
    if mime_type == "application/pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        result = []
        for page_num in range(min(len(doc), 5)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            png_bytes = pix.tobytes("png")
            b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
            result.append((b64, "image/png"))
        doc.close()
        return result

    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
    return [(b64, mime_type)]


def extract_document(file_bytes: bytes, mime_type: str, api_key: str) -> dict:
    """Send document to Claude Vision and return extracted data."""
    images = file_to_images(file_bytes, mime_type)

    content = []
    for img_b64, img_media_type in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img_media_type,
                "data": img_b64,
            },
        })
    content.append({"type": "text", "text": EXTRACTION_PROMPT})

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    return json.loads(raw_text)


def result_to_csv(results: list[dict]) -> str:
    """Convert extraction results to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")  # semicolon for Dutch Excel

    # Header
    writer.writerow([
        "Leverancier", "Factuurnummer", "Factuurdatum", "Vervaldatum",
        "Totaal (incl. BTW)", "BTW bedrag", "BTW %", "Valuta", "IBAN",
        "Regelomschrijving", "Aantal", "Stukprijs", "Regeltotaal",
    ])

    for r in results:
        items = r.get("line_items") or [{}]
        if not items:
            items = [{}]
        for item in items:
            writer.writerow([
                r.get("vendor_name", ""),
                r.get("invoice_number", ""),
                r.get("invoice_date", ""),
                r.get("due_date", ""),
                r.get("total_amount", ""),
                r.get("vat_amount", ""),
                r.get("vat_percentage", ""),
                r.get("currency", "EUR"),
                r.get("iban", ""),
                item.get("description", ""),
                item.get("quantity", ""),
                item.get("unit_price", ""),
                item.get("total", ""),
            ])

    return output.getvalue()


def format_eur(value) -> str:
    """Format a number as EUR currency."""
    if value is None:
        return "-"
    return f"\u20ac {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

# Sidebar
with st.sidebar:
    st.markdown("## DocStream")
    st.caption("AI-powered factuur extractie voor ZZP'ers en MKB")
    st.divider()

    st.markdown(f"**Verwerkt deze sessie:** {len(st.session_state.history)}")

    if st.session_state.history:
        st.divider()
        csv_data = result_to_csv(st.session_state.history)
        st.download_button(
            label="Download alles als CSV",
            data=csv_data,
            file_name="docstream_export.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()
    st.markdown(
        "**Ondersteunde bestanden:**\n"
        "- PDF\n"
        "- PNG / JPG / WebP\n\n"
        "**Max bestandsgrootte:** 20MB"
    )

# Main content
st.title("Factuur & Bon Extractor")
st.markdown("Upload een factuur of bon en krijg direct gestructureerde data terug.")

uploaded_file = st.file_uploader(
    "Sleep je bestand hierheen of klik om te uploaden",
    type=["pdf", "png", "jpg", "jpeg", "webp"],
    help="PDF, PNG, JPG of WebP — max 20MB",
)

if uploaded_file is not None:
    mime = uploaded_file.type
    if mime not in ALLOWED_TYPES:
        st.error(f"Bestandstype `{mime}` wordt niet ondersteund.")
    else:
        col_preview, col_result = st.columns([1, 1])

        with col_preview:
            st.markdown("### Document")
            if mime == "application/pdf":
                # Show first page as image
                doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                st.image(pix.tobytes("png"), use_container_width=True)
                if len(doc) > 1:
                    st.caption(f"Pagina 1 van {len(doc)}")
                doc.close()
            else:
                st.image(uploaded_file, use_container_width=True)

        with col_result:
            st.markdown("### Extractie")

            api_key = get_api_key()

            with st.spinner("Document wordt geanalyseerd door AI..."):
                try:
                    data = extract_document(uploaded_file.getvalue(), mime, api_key)
                except json.JSONDecodeError:
                    st.error("Kon het AI-antwoord niet verwerken. Probeer opnieuw.")
                    st.stop()
                except Exception as e:
                    st.error(f"Fout bij extractie: {e}")
                    st.stop()

            # Confidence indicator
            confidence = data.get("confidence", 0)
            if confidence >= 0.8:
                st.success(f"Betrouwbaarheid: {confidence:.0%}")
            elif confidence >= 0.5:
                st.warning(f"Betrouwbaarheid: {confidence:.0%} — controleer de data")
            else:
                st.error(f"Betrouwbaarheid: {confidence:.0%} — mogelijk geen factuur")

            # Key fields
            st.markdown("**Leverancier**")
            st.code(data.get("vendor_name") or "-")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Factuurnummer**")
                st.code(data.get("invoice_number") or "-")
                st.markdown("**Factuurdatum**")
                st.code(data.get("invoice_date") or "-")
            with c2:
                st.markdown("**Vervaldatum**")
                st.code(data.get("due_date") or "-")
                st.markdown("**IBAN**")
                st.code(data.get("iban") or "-")

            st.divider()

            # Amounts
            a1, a2, a3 = st.columns(3)
            with a1:
                st.metric("Subtotaal", format_eur(
                    (data.get("total_amount") or 0) - (data.get("vat_amount") or 0)
                ))
            with a2:
                pct = data.get("vat_percentage")
                label = f"BTW ({pct:.0f}%)" if pct else "BTW"
                st.metric(label, format_eur(data.get("vat_amount")))
            with a3:
                st.metric("Totaal", format_eur(data.get("total_amount")))

            # Line items
            items = data.get("line_items") or []
            if items:
                st.divider()
                st.markdown("**Regelitems**")
                for i, item in enumerate(items, 1):
                    with st.container():
                        ic1, ic2, ic3 = st.columns([3, 1, 1])
                        with ic1:
                            st.text(f"{i}. {item.get('description', '-')}")
                        with ic2:
                            qty = item.get("quantity")
                            price = item.get("unit_price")
                            if qty and price:
                                st.text(f"{qty:.0f} x {format_eur(price)}")
                        with ic3:
                            st.text(format_eur(item.get("total")))

        # Add to history
        if data not in st.session_state.history:
            st.session_state.history.append(data)

        # Download buttons
        st.divider()
        dl1, dl2, dl3 = st.columns(3)

        with dl1:
            csv_single = result_to_csv([data])
            st.download_button(
                label="Download CSV",
                data=csv_single,
                file_name=f"factuur_{data.get('invoice_number', 'export')}.csv",
                mime="text/csv",
            )
        with dl2:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"factuur_{data.get('invoice_number', 'export')}.json",
                mime="application/json",
            )
        with dl3:
            if len(st.session_state.history) > 1:
                csv_all = result_to_csv(st.session_state.history)
                st.download_button(
                    label=f"Download alles ({len(st.session_state.history)} facturen)",
                    data=csv_all,
                    file_name="docstream_alle_facturen.csv",
                    mime="text/csv",
                )
