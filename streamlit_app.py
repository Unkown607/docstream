"""Receiptly — AI Factuur Extractor voor ZZP'ers en MKB."""

import base64
import csv
import hashlib
import io
import json
import logging
from datetime import datetime, timezone

import fitz  # PyMuPDF
import streamlit as st
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Receiptly — Factuur Extractor",
    page_icon="📄",
    layout="wide",
)

EXTRACTION_PROMPT = """Je bent een expert document-extractor gespecialiseerd in Nederlandse en Europese facturen en bonnen.
Je kunt ook Engelse en andere Europese facturen verwerken.

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
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass
    from dotenv import dotenv_values
    env = dotenv_values(".env")
    key = env.get("ANTHROPIC_API_KEY", "")
    if not key:
        st.error("Geen Anthropic API key gevonden. Stel Streamlit Secrets in of maak een `.env` bestand aan.")
        st.stop()
    return key


@st.cache_resource
def get_client() -> Anthropic:
    """Create a cached Anthropic client (reused across reruns)."""
    return Anthropic(api_key=get_api_key())


def file_hash(file_bytes: bytes) -> str:
    """Return a short hash for deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()[:16]


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


def extract_document(file_bytes: bytes, mime_type: str) -> dict:
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

    client = get_client()
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )
    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            st.error("API rate limit bereikt. Wacht even en probeer opnieuw.")
        elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
            st.error("Ongeldige API key. Controleer je instellingen.")
        else:
            st.error(f"API fout: {error_msg}")
        st.stop()

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse response: %s", raw_text[:500])
        st.error("Kon het AI-antwoord niet verwerken. Probeer opnieuw.")
        st.stop()


def result_to_csv(results: list[dict]) -> str:
    """Convert extraction results to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

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


def track_event(event: str, details: str = "") -> None:
    """Simple analytics: log events and store counters in session state."""
    if "analytics" not in st.session_state:
        st.session_state.analytics = {"uploads": 0, "extractions": 0, "exports": 0}

    if event in st.session_state.analytics:
        st.session_state.analytics[event] += 1

    logger.info("ANALYTICS | %s | %s | %s", event, details, datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "history" not in st.session_state:
    st.session_state.history = []

if "cache" not in st.session_state:
    st.session_state.cache = {}  # file_hash -> extraction result

if "analytics" not in st.session_state:
    st.session_state.analytics = {"uploads": 0, "extractions": 0, "exports": 0}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

# Sidebar
with st.sidebar:
    st.markdown("## Receiptly")
    st.caption("AI-powered factuur extractie voor ZZP'ers en MKB")
    st.divider()

    uploads = st.session_state.analytics.get("uploads", 0)
    extractions = st.session_state.analytics.get("extractions", 0)
    exports = st.session_state.analytics.get("exports", 0)

    st.markdown(f"**Verwerkt:** {len(st.session_state.history)} facturen")
    st.caption(f"Uploads: {uploads} | Extracties: {extractions} | Exports: {exports}")

    if st.session_state.history:
        st.divider()
        csv_data = result_to_csv(st.session_state.history)
        if st.download_button(
            label="Download alles als CSV",
            data=csv_data,
            file_name="receiptly_export.csv",
            mime="text/csv",
            use_container_width=True,
        ):
            track_event("exports", f"bulk_{len(st.session_state.history)}")

    st.divider()
    st.markdown(
        "**Ondersteunde bestanden:**\n"
        "- PDF\n"
        "- PNG / JPG / WebP\n\n"
        "**Max bestandsgrootte:** 20MB"
    )
    st.divider()
    st.caption("Novex HQ | [info@novexhq.com](mailto:info@novexhq.com)")

# Main content
st.title("Factuur & Bon Extractor")
st.markdown("Upload een of meerdere facturen en krijg direct gestructureerde data terug.")

uploaded_files = st.file_uploader(
    "Sleep je bestanden hierheen of klik om te uploaden",
    type=["pdf", "png", "jpg", "jpeg", "webp"],
    help="PDF, PNG, JPG of WebP — max 20MB per bestand",
    accept_multiple_files=True,
)

if uploaded_files:
    for file_idx, uploaded_file in enumerate(uploaded_files):
        mime = uploaded_file.type
        if mime not in ALLOWED_TYPES:
            st.error(f"**{uploaded_file.name}**: bestandstype `{mime}` wordt niet ondersteund.")
            continue

        file_bytes = uploaded_file.getvalue()
        fhash = file_hash(file_bytes)
        track_event("uploads", uploaded_file.name)

        if len(uploaded_files) > 1:
            st.divider()
            st.subheader(f"📄 {uploaded_file.name}")

        col_preview, col_result = st.columns([1, 1])

        with col_preview:
            st.markdown("### Document")
            if mime == "application/pdf":
                doc = fitz.open(stream=file_bytes, filetype="pdf")
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

            # Check cache to avoid re-extraction
            if fhash in st.session_state.cache:
                data = st.session_state.cache[fhash]
                st.caption("(uit cache — geen extra API kosten)")
            else:
                with st.spinner("Document wordt geanalyseerd door AI..."):
                    data = extract_document(file_bytes, mime)
                    st.session_state.cache[fhash] = data
                    track_event("extractions", uploaded_file.name)

            # Confidence indicator
            confidence = data.get("confidence", 0)
            if confidence >= 0.8:
                st.success(f"Betrouwbaarheid: {confidence:.0%}")
            elif confidence >= 0.5:
                st.warning(f"Betrouwbaarheid: {confidence:.0%} — controleer de data")
            else:
                st.error(f"Betrouwbaarheid: {confidence:.0%} — mogelijk geen factuur")

            # Editable fields
            edit_key = f"edit_{fhash}_{file_idx}"

            vendor = st.text_input(
                "Leverancier",
                value=data.get("vendor_name") or "",
                key=f"{edit_key}_vendor",
            )
            data["vendor_name"] = vendor

            ec1, ec2 = st.columns(2)
            with ec1:
                inv_nr = st.text_input(
                    "Factuurnummer",
                    value=data.get("invoice_number") or "",
                    key=f"{edit_key}_invnr",
                )
                data["invoice_number"] = inv_nr

                inv_date = st.text_input(
                    "Factuurdatum",
                    value=data.get("invoice_date") or "",
                    key=f"{edit_key}_date",
                )
                data["invoice_date"] = inv_date
            with ec2:
                due = st.text_input(
                    "Vervaldatum",
                    value=data.get("due_date") or "",
                    key=f"{edit_key}_due",
                )
                data["due_date"] = due

                iban = st.text_input(
                    "IBAN",
                    value=data.get("iban") or "",
                    key=f"{edit_key}_iban",
                )
                data["iban"] = iban

            st.divider()

            # Editable amounts
            ea1, ea2, ea3 = st.columns(3)
            with ea1:
                total = st.number_input(
                    "Totaal (incl. BTW)",
                    value=float(data.get("total_amount") or 0),
                    format="%.2f",
                    key=f"{edit_key}_total",
                )
                data["total_amount"] = total
            with ea2:
                vat = st.number_input(
                    "BTW bedrag",
                    value=float(data.get("vat_amount") or 0),
                    format="%.2f",
                    key=f"{edit_key}_vat",
                )
                data["vat_amount"] = vat
            with ea3:
                vat_pct = st.number_input(
                    "BTW %",
                    value=float(data.get("vat_percentage") or 0),
                    format="%.1f",
                    key=f"{edit_key}_vatpct",
                )
                data["vat_percentage"] = vat_pct

            st.caption(f"Subtotaal: {format_eur(total - vat)}")

            # Line items (read-only display)
            items = data.get("line_items") or []
            if items:
                st.divider()
                st.markdown("**Regelitems**")
                for i, item in enumerate(items, 1):
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

        # Update cache with edits
        st.session_state.cache[fhash] = data

        # Add to history (deduplicate by hash)
        existing_hashes = [h.get("_hash") for h in st.session_state.history]
        if fhash not in existing_hashes:
            data["_hash"] = fhash
            data["_filename"] = uploaded_file.name
            st.session_state.history.append(data)

        # Download buttons
        st.divider()
        dl1, dl2 = st.columns(2)

        with dl1:
            csv_single = result_to_csv([data])
            if st.download_button(
                label="Download CSV",
                data=csv_single,
                file_name=f"factuur_{data.get('invoice_number', 'export')}.csv",
                mime="text/csv",
                key=f"dl_csv_{fhash}_{file_idx}",
            ):
                track_event("exports", uploaded_file.name)
        with dl2:
            export_data = {k: v for k, v in data.items() if not k.startswith("_")}
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
            if st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"factuur_{data.get('invoice_number', 'export')}.json",
                mime="application/json",
                key=f"dl_json_{fhash}_{file_idx}",
            ):
                track_event("exports", uploaded_file.name)

    # Bulk export at the bottom if multiple files
    if len(uploaded_files) > 1 and st.session_state.history:
        st.divider()
        st.subheader(f"Bulk export — {len(st.session_state.history)} facturen")
        csv_all = result_to_csv(st.session_state.history)
        if st.download_button(
            label="Download alles als CSV",
            data=csv_all,
            file_name="receiptly_alle_facturen.csv",
            mime="text/csv",
            key="dl_bulk",
            use_container_width=True,
        ):
            track_event("exports", f"bulk_{len(st.session_state.history)}")
