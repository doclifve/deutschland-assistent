<p align="center">
  <img src="assets/logo-animated.svg" alt="Deutschland Assistent Logo: drei Kreise in Schwarz, Rot und Gold, die atmen und sich langsam drehen" width="220" />
</p>

# Deutschland Assistent 🇩🇪

**Open-source civic assistance for Germany: understand documents, laws, public services and next steps — with evidence.**

Deutschland Assistent is an open-source, evidence-first civic assistant. It is designed to make German public administration, laws and personal documents easier to understand without requiring users to know legal terms, agency names or AI prompting.

> **Core principle:** The model is not the source of truth. Official sources and the user's document are.

<p align="center">
  <img src="docs/screenshots/iphone.png" alt="Deutschland Assistent auf dem iPhone: Startseite mit animiertem Logo, „So einfach.“ in drei Schritten und Ergebnis mit geschätzter Widerspruchsfrist und amtlichen Quellen" width="860" />
</p>

<details>
<summary>iPad</summary>
<p align="center">
  <img src="docs/screenshots/ipad.png" alt="Deutschland Assistent auf dem iPad: Startseite mit animiertem Logo und der Überschrift „Behördenpost. Endlich verständlich.“" width="760" />
</p>
</details>

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
- Connect via WhatsApp: the web app shows a button and QR code from `GET /v1/channels`; the adapter answers photos, PDFs and questions in the chat.
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

### Option B — without Docker

Requires Python 3.11+ (on macOS: `python3.12`, not `python`) and Node.js 20+.

Backend, in one terminal:

```bash
cd services/civic-core
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m uvicorn deutschland_assistent.main:app --reload --port 8000
```

`python -m uvicorn` makes sure the server runs from the virtual environment, even if an older global `uvicorn` is installed.

Web interface, in a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

Then open http://localhost:3000 (API docs: http://localhost:8000/docs).

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
- `GET /v1/channels` — public connection details for messaging channels (WhatsApp number and `wa.me` link). Never contains tokens or secrets.
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
| `WHATSAPP_PUBLIC_NUMBER` | – | Public WhatsApp number in E.164 format (`+4915123456789`). Enables the WhatsApp section and QR code in the web app; empty hides it |
| `WHATSAPP_GREETING` | `Hallo` | Text pre-filled in the chat when someone opens the `wa.me` link |
| `WHATSAPP_APP_SECRET` | – | Verifies Meta's `X-Hub-Signature-256`; required when `APP_ENV=production` |
| `MAX_WHATSAPP_MEDIA_BYTES` | `15728640` | Maximum WhatsApp media size accepted by the adapter |

## WhatsApp

<p align="center">
  <img src="docs/screenshots/whatsapp.png" alt="WhatsApp-Verbindung: Abschnitt „Einfach per WhatsApp.“ in der Web-App, Begrüßung im Chat und Antwort auf ein fotografiertes Schreiben mit Frist, nächsten Schritten und amtlicher Quelle" width="860" />
</p>

Citizens can use the assistant directly in WhatsApp: send a photo or PDF of a letter, optionally with a question, and get the deadline, next steps and official sources back as a chat message. *(The chat on the right is a schematic rendering of the adapter's real reply text; in WhatsApp it appears in the usual chat view.)*

How the pieces connect:

```text
Web app ──GET /v1/channels──▶ Civic Core          (public number, wa.me link → button + QR code)
WhatsApp ──webhook──▶ whatsapp-cloud adapter ──▶ Civic Core /v1/documents, /v1/ask
                              │
                              └──▶ WhatsApp Cloud API (reply)
```

- **Web app:** shows "Einfach per WhatsApp." with an *In WhatsApp öffnen* button and, on tablet and desktop, a QR code — only when `WHATSAPP_PUBLIC_NUMBER` is set.
- **Adapter** (`channels/whatsapp-cloud/`): verifies Meta's webhook signature, accepts text, photos and PDFs, answers greetings such as "Hallo" or "Hilfe" with a short how-to, and replies with the core's answer.

### Setting it up

1. In the Meta developer dashboard, create an app with the **WhatsApp** product and register a business phone number. Note the *phone number ID*, a permanent *access token* and the app's *app secret*.
2. Fill in `.env`:
   ```bash
   WHATSAPP_PUBLIC_NUMBER=+4915123456789   # the number people write to
   WHATSAPP_PHONE_NUMBER_ID=...
   WHATSAPP_ACCESS_TOKEN=...
   WHATSAPP_APP_SECRET=...
   WHATSAPP_VERIFY_TOKEN=<a long random string>
   ```
3. Start everything including the adapter:
   ```bash
   docker compose --profile whatsapp up --build
   ```
4. Expose the adapter over HTTPS (for local testing e.g. with a tunnel such as `cloudflared` or `ngrok` pointing at port 8010) and enter `https://<your-host>/webhook` plus your `WHATSAPP_VERIFY_TOKEN` as the webhook in the Meta dashboard. Subscribe to the **messages** field.
5. Send "Hallo" to your number. You should get the welcome message back.

Messages pass through WhatsApp (Meta), so the privacy notice in the web app says so. Documents are deleted from the core after `DOCUMENT_TTL_SECONDS`.

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
