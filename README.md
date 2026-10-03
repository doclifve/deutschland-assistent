<p align="center">
  <img src="assets/logo-animated.svg" alt="Deutschland Assistent Logo: drei Kreise in Schwarz, Rot und Gold, die atmen und sich langsam drehen" width="220" />
</p>

# Deutschland Assistent 🇩🇪

**Open-source civic assistance for Germany: understand documents, laws, public services and next steps — with evidence.**

Deutschland Assistent is an open-source, evidence-first civic assistant. It is designed to make German public administration, laws and personal documents easier to understand without requiring users to know legal terms, agency names or AI prompting.

> **Core principle:** The model is not the source of truth. Official sources and the user's document are.

## What v0.2.2 can do

- Upload PDFs, text files **and photos/scans**.
- Extract text, dates, deadlines and common legal references.
- Analyze documents without any LLM or API key.
- Use **Docling locally** for OCR and layout-aware parsing of photos, scans and text-poor PDFs; remote Docling services are disabled.
- Extract deadlines, legal references, LeiKa identifiers, authority hints, **requested documents/actions/payments** and **Rechtsbehelfsbelehrungen** deterministically.
- Recognise relative deadlines from *Rechtsbehelfsbelehrungen* ("innerhalb eines Monats nach Bekanntgabe") and estimate the end date conservatively from the letter date (4-day postal fiction since 1 Jan 2025, §§ 187 f. BGB, weekend shift). Estimates are always flagged `confidence: low` with their calculation basis.
- Hold uploaded documents only in memory, with an expiry (`DOCUMENT_TTL_SECONDS`, default 1 h), a size cap and an explicit `DELETE /v1/documents/{id}`.
- Resolve explicit law citations through **Gesetze im Internet**.
- Search current federal legislation **and federal case law** through the official **NeuRIS** API, with a direct-law fallback because NeuRIS is still in test phase and incomplete.
- Match common benefits/services against an auditable registry of official federal sources.
- Return structured, ranked evidence with every important source.
- Ask questions through a simple web interface.
- Provide an OpenClaw skill for WhatsApp/Telegram/Signal-style access.
- Accept text, **photos and documents over the WhatsApp Cloud API adapter**, verify Meta webhook signatures and forward media through the same evidence-first document pipeline.
- Keep channel integrations separate from the civic core.

### What a document answer contains

For a photographed authority letter the API can now return, separately:

- the document/authority type,
- explicit and relative deadlines,
- requested documents, information, payments or actions,
- detected appeal/remedy instructions,
- cited statutes,
- relevant official legislation and case law,
- a citizen-facing next-step list with uncertainty preserved.

## Product idea

A citizen should be able to send a photo or PDF and get:

1. **What is this?**
2. **What does it mean?**
3. **What do I need to do?**
4. **Is there a deadline?**
5. **Which law/source supports this?**
6. **What is unclear or missing?**

The UI should remain simple even as the backend becomes more capable.

## Architecture

```text
                      Citizen
                         │
        ┌────────────────┼────────────────┐
        │                │                │
       Web            OpenClaw       WhatsApp Cloud
        │          (WA/TG/Signal)          │
        └────────────────┼────────────────┘
                         ▼
                  Channel Gateway
                         │
                         ▼
              Deutschland Assistent Core
       Intent → Document → Retrieval → Evidence
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
           Docling     Legal      Services
             OCR      sources      sources
                         │
                         ▼
                   Answer schema
                         │
                         ▼
                  Human-readable UI
```

### Architectural rules

- **Channels are adapters.** OpenClaw/WhatsApp do not contain legal logic.
- **Evidence is first-class.** Claims point back to a document location or official source.
- **Actions require confirmation.** v0.1 does not autonomously submit applications, objections, cancellations or other legally relevant declarations.
- **No provider lock-in.** The core works without an LLM; model providers can be added behind an interface.
- **Minimal retention.** Personal documents should be processed ephemerally by default in production.

## Quick start

### Option A — Docker

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Option B — backend only

```bash
cd services/civic-core
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn deutschland_assistent.main:app --reload --port 8000
```

For Docling/OCR support:

```bash
pip install -e '.[docling]'
```

## Example API

```bash
curl -X POST http://localhost:8000/v1/ask \
  -H 'Content-Type: application/json' \
  -d '{"message":"Was bedeutet § 60 SGB I?","language":"de"}'
```

Upload a PDF:

```bash
curl -X POST http://localhost:8000/v1/documents \
  -F 'file=@bescheid.pdf'
```

## Evidence Engine API

- `POST /v1/evidence/search` — search the official-source layer directly.
- `GET /v1/sources` — inspect source roles/status.
- `POST /v1/documents` — parse a citizen document and extract deterministic facts.
- `DELETE /v1/documents/{id}` — remove an uploaded document before it expires.
- `POST /v1/ask` — combine document facts with official evidence.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call the API |
| `DOCUMENT_ENGINE` | `auto` | `basic`, `docling` or `auto` |
| `MAX_UPLOAD_BYTES` | `15728640` | Upload size limit |
| `MAX_DOCUMENT_PAGES` | `30` | Maximum pages per document |
| `DOCLING_ARTIFACTS_PATH` | `/opt/docling-models` | Local Docling model cache |
| `PREFETCH_DOCLING_MODELS` | `0` | Set to `1` at image build time to prefetch Docling models |
| `DOCUMENT_TTL_SECONDS` | `3600` | How long an uploaded document stays in memory |
| `MAX_STORED_DOCUMENTS` | `500` | Upper bound for documents held at once |
| `WHATSAPP_APP_SECRET` | – | Verifies Meta's `X-Hub-Signature-256`; required when `APP_ENV=production` |
| `MAX_WHATSAPP_MEDIA_BYTES` | `15728640` | Maximum WhatsApp media size accepted by the adapter |

## OpenClaw

The repository includes an installable OpenClaw skill under `channels/openclaw/deutschland-assistent/`.

```bash
openclaw skills install ./channels/openclaw/deutschland-assistent --as deutschland-assistent
```

Set:

```bash
export DEUTSCHLAND_ASSISTENT_API=http://localhost:8000
```

The OpenClaw integration is intentionally narrow: it forwards civic questions and document-analysis requests to the core API. Keep unrestricted shell/browser/file tools disabled for public-facing agents.

For current OpenClaw channel setup, see the upstream OpenClaw documentation. WhatsApp is an optional official OpenClaw channel plugin; production public deployments should also consider the official WhatsApp Cloud API adapter included here.

## Repository layout

```text
apps/web/                                   Minimal citizen-facing web UI
services/civic-core/                        FastAPI civic core
  deutschland_assistent/extraction.py       Deterministic extraction (references, deadlines, LeiKa)
  deutschland_assistent/evidence.py         Official-source Evidence Engine (Gesetze im Internet, NeuRIS, Bundesportal)
  deutschland_assistent/documents.py        Document parsing (pypdf, optional Docling)
  deutschland_assistent/schemas.py          Answer and evidence schema
channels/openclaw/                          Installable OpenClaw skill
channels/whatsapp-cloud/                    Official WhatsApp Cloud API adapter scaffold
docs/                                       Architecture, security, source policy
```

Planned (not yet in the repository): `skills/` for domain workflows, `evals/` for safety and quality tests.

## Data sources

The initial source registry is deliberately conservative and points to official German sources. Connector code should only be promoted to `authoritative` once its API/format contract is pinned and tested.

Planned/initial sources include:

- Gesetze im Internet
- Rechtsinformationssystem des Bundes (NeuRIS / recht.bund.de)
- Bundesportal
- Bundesagentur für Arbeit
- Deutsche Rentenversicherung

See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Safety and legal boundaries

This project is designed for **information access and assistance**, not autonomous legal decision-making. It must not claim that a user definitely has or does not have a legal entitlement based solely on model output. High-impact actions must be previewed and explicitly confirmed by a human.

See:

- [Security](SECURITY.md)
- [Source policy](SOURCE_POLICY.md)
- [Model policy](MODEL_POLICY.md)
- [Transparency](TRANSPARENCY.md)
- [Threat model](docs/THREAT_MODEL.md)

## Development

```bash
make test
```

The deterministic extraction tests cover explicit and relative deadlines, document dates and legal references. Add an eval before adding a new high-impact workflow.

## Status

**v0.2.2 early alpha.** OCR document intelligence, structured demands/appeal extraction and NeuRIS case-law retrieval are implemented; APIs and schemas may still change.

## License

Apache-2.0 for original project code unless a file says otherwise. External components and data sources retain their own licenses and terms.


## Logo motion

The logo is intentionally alive: the three black, red and gold circles breathe apart and back together with a slight phase shift (3 s cycle, 0.3 s offset) while the whole cluster rotates slowly (12 s). Red and gold are slightly translucent, so their overlaps change color as the circles move. Motion is disabled automatically when the operating system requests reduced motion.

The README uses `assets/logo-animated.svg`, a self-contained animated SVG (CSS only, no scripts), so it also animates on GitHub. `assets/logo.svg` remains the static version for places that cannot show animation. The animated logo has a transparent background; in dark mode the black circle gets a subtle light outline so it stays visible.
