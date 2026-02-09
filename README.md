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

- **Google login** — Authenticatie via OIDC, sessies bewaard via cookie
- **Drag & drop upload** — PDF, PNG, JPG of WebP
- **AI-extractie** — Leverancier, factuurnummer, datum, bedragen, BTW, IBAN, regelitems
- **Nederlandse focus** — Geoptimaliseerd voor NL/EU factuurformaten
- **Persistente opslag** — Extractiegeschiedenis bewaard in Supabase (PostgreSQL)
- **Gebruikslimieten** — Free tier: 10 extracties/maand, opschaalbaar per plan
- **CSV export** — Puntkomma-gescheiden, direct importeerbaar in Excel en boekhoudsoftware
- **JSON export** — Voor ontwikkelaars en automatisering
- **Bulk verwerking** — Meerdere facturen per sessie, download alles in 1 CSV
- **Betrouwbaarheidsscore** — Weet direct of de extractie gecontroleerd moet worden
- **REST API** — Beveiligde FastAPI backend met API key auth voor integraties

---

## Quick Start

### Online (Streamlit Cloud)

[https://docstream-nuycd3h4sngvymjscxct36.streamlit.app/](https://docstream-nuycd3h4sngvymjscxct36.streamlit.app/)

### Lokaal draaien

```bash
git clone https://github.com/Unkown607/docstream.git
cd docstream
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 1. Supabase database

Maak een project aan op [supabase.com](https://supabase.com) en voer `schema.sql` uit in de SQL Editor.

#### 2. Google OAuth

Maak een OAuth 2.0 Client ID aan in de [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
Voeg `http://localhost:8501/oauth2callback` toe als redirect URI.

#### 3. Secrets configureren

Kopieer `.env.example` naar `.env` en vul in:

```env
ANTHROPIC_API_KEY=sk-ant-...
API_KEY=<genereer met: python -c "import secrets; print(secrets.token_urlsafe(32))">
```

Vul `.streamlit/secrets.toml` in met Supabase + Google OIDC credentials (zie template).

#### 4. Start de Streamlit app

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501` → log in met Google → upload een factuur.

### API starten

```bash
uvicorn app.main:app --reload
```

API docs beschikbaar op `http://localhost:8000/docs`.

Alle `/api/` endpoints vereisen een API key:

```bash
curl -H "Authorization: Bearer <jouw-api-key>" http://localhost:8000/api/v1/documents/
```

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
  -H "Authorization: Bearer <jouw-api-key>" \
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
| Auth | Google OIDC via `st.login()` + Authlib |
| Backend | FastAPI (Python) + API key auth |
| AI | Claude Vision API (Anthropic) |
| PDF verwerking | PyMuPDF |
| Database | Supabase (PostgreSQL) + SQLAlchemy/SQLite (API) |
| Config | Pydantic Settings |

---

## Projectstructuur

```
docstream/
├── streamlit_app.py        # Streamlit frontend (auth + extractie UI)
├── supabase_client.py      # Supabase helpers (users, usage, documents)
├── schema.sql              # Database schema voor Supabase SQL Editor
├── app/
│   ├── main.py             # FastAPI entrypoint + CORS + API key auth
│   ├── config.py           # Pydantic settings (incl. security config)
│   ├── database.py         # Async database setup
│   ├── models.py           # SQLAlchemy modellen
│   ├── schemas.py          # Pydantic schemas
│   ├── extraction.py       # AI extractie pipeline
│   ├── storage.py          # Bestandsopslag (extension allowlist, chunked upload)
│   └── routes.py           # API routes (UUID-validated)
├── .streamlit/
│   ├── config.toml         # Streamlit thema
│   └── secrets.toml        # Secrets (gitignored)
├── requirements.txt
└── .env.example
```

---

## Roadmap

- [x] Core AI extractie pipeline
- [x] FastAPI REST backend + API key auth
- [x] Streamlit frontend met drag & drop
- [x] CSV & JSON export
- [x] Gebruikersaccounts (Google OIDC)
- [x] Persistente opslag (Supabase PostgreSQL)
- [x] Gebruikslimieten per plan (free/pro/unlimited)
- [x] E-mail inboxverwerking (scan@novexhq.com)
- [x] Security hardening (CORS, auth, CVE fixes, chunked uploads)
- [ ] Stripe betalingsintegratie
- [ ] Directe koppeling met Moneybird, e-Boekhouden, Exact Online
- [ ] Rate limiting op API

---

## Licentie

MIT

---

Gebouwd met Python en Claude AI.
