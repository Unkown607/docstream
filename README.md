# DocStream

**AI-powered factuur & bon extractie voor ZZP'ers en MKB.**

Upload een factuur of bon (PDF, foto) en krijg direct gestructureerde data terug — leverancier, bedragen, BTW, regelitems. Exporteer als CSV voor je boekhouding.

---

## Het probleem

Elke maand hetzelfde verhaal: stapels facturen en bonnen handmatig overtypen in je boekhouding. Fouten, tijdverlies, en frustratie.

## De oplossing

DocStream leest je documenten met AI en geeft je binnen seconden een schone dataset terug. Upload, controleer, exporteer. Klaar.

---

## Features

- **Drag & drop upload** — PDF, PNG, JPG of WebP
- **AI-extractie** — Leverancier, factuurnummer, datum, bedragen, BTW, IBAN, regelitems
- **Nederlandse focus** — Geoptimaliseerd voor NL/EU factuurformaten
- **CSV export** — Puntkomma-gescheiden, direct importeerbaar in Excel en boekhoudsoftware
- **JSON export** — Voor ontwikkelaars en automatisering
- **Bulk verwerking** — Meerdere facturen per sessie, download alles in 1 CSV
- **Betrouwbaarheidsscore** — Weet direct of de extractie gecontroleerd moet worden
- **REST API** — Volledige FastAPI backend voor integraties

---

## Quick Start

### Online (Streamlit Cloud)

> Link volgt na deployment

### Lokaal draaien

```bash
git clone https://github.com/Unkown607/docstream.git
cd docstream
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Maak een `.env` bestand aan:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Start de app:

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in je browser.

### API starten

```bash
uvicorn app.main:app --reload
```

API docs beschikbaar op `http://localhost:8000/docs`.

---

## API Endpoints

| Method | Endpoint | Functie |
|--------|----------|---------|
| `POST` | `/api/v1/documents/upload` | Upload + AI extractie |
| `GET` | `/api/v1/documents/` | Lijst alle documenten |
| `GET` | `/api/v1/documents/{id}` | Enkel document ophalen |
| `DELETE` | `/api/v1/documents/{id}` | Document verwijderen |
| `GET` | `/health` | Health check |

### Voorbeeld

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@factuur.pdf;type=application/pdf"
```

Response:

```json
{
  "id": "9e39089d-...",
  "filename": "factuur.pdf",
  "status": "completed",
  "extraction": {
    "vendor_name": "TechBouw B.V.",
    "invoice_number": "INV-2026-0042",
    "invoice_date": "2026-02-09",
    "total_amount": 6013.10,
    "vat_amount": 1043.60,
    "vat_percentage": 21.0,
    "currency": "EUR",
    "iban": "NL91ABNA0417164300",
    "line_items": [
      {
        "description": "Webontwikkeling",
        "quantity": 40,
        "unit_price": 85.00,
        "total": 3400.00
      }
    ],
    "confidence": 0.92
  }
}
```

---

## Tech Stack

| Component | Technologie |
|-----------|------------|
| Frontend | Streamlit |
| Backend | FastAPI (Python) |
| AI | Claude Vision API (Anthropic) |
| PDF verwerking | PyMuPDF |
| Database | SQLAlchemy + SQLite (async) |
| Config | Pydantic Settings |

---

## Projectstructuur

```
docstream/
├── streamlit_app.py        # Frontend UI
├── app/
│   ├── main.py             # FastAPI entrypoint
│   ├── config.py           # Configuratie
│   ├── database.py         # Async database setup
│   ├── models.py           # SQLAlchemy modellen
│   ├── schemas.py          # Pydantic schemas
│   ├── extraction.py       # AI extractie pipeline
│   ├── storage.py          # Bestandsopslag
│   └── routes.py           # API routes
├── .streamlit/config.toml  # Streamlit thema
├── requirements.txt
└── .env.example
```

---

## Roadmap

- [x] Core AI extractie pipeline
- [x] FastAPI REST backend
- [x] Streamlit frontend met drag & drop
- [x] CSV & JSON export
- [ ] Gebruikersaccounts & authenticatie
- [ ] Stripe betalingsintegratie
- [ ] Directe koppeling met Moneybird, e-Boekhouden, Exact Online
- [ ] Batch upload (meerdere bestanden tegelijk)
- [ ] E-mail inboxverwerking (stuur facturen naar scan@docstream.nl)

---

## Licentie

MIT

---

Gebouwd met Python en Claude AI.
