---
name: api-endpunkt
description: Neuen Endpunkt im Civic Core (FastAPI, services/civic-core/deutschland_assistent/main.py) anlegen oder ändern, inkl. Pydantic-Schemas, Fehlermeldungen, Datei-Uploads/-Downloads und Anbindung im Next.js-Frontend. Verwenden für jede API-Änderung.
---
# API-Endpunkt

## Konventionen
- Pfad `/v1/...`, Request/Response als Pydantic-Modelle in `schemas.py`, `response_model=` setzen.
- Fehlermeldungen auf **Deutsch**, als `HTTPException(status, "Text.")`. Codes: 400 leer, 404 nicht gefunden/abgelaufen,
  409 Versionskonflikt, 413 zu groß, 415 Format, 422 Inhalt, 503 LLM/Connector nicht konfiguriert.
- Uploads: `await file.read(MAX + 1)` und Größe prüfen; CPU-lastiges Parsen (pypdf, Docling) mit
  `await run_in_threadpool(...)` – nie blockierend im `async def`.
- Downloads: Header immer über `attachment_headers(filename)` bauen (latin-1-sicher, RFC 5987) – nie
  den Dateinamen roh in `Content-Disposition` schreiben (führt bei Umlauten/Kyrillisch zu HTTP 500).
- Speicher nur im RAM mit TTL (`DocumentStore`, `FormStore`, `ActionStore`); keine Dateien auf Platte, keine Logs mit Inhalten.
- Externe/LLM-Fehler als `ModelProviderError` fangen und deterministisch weiterantworten.
- Sprachmodell nie über das globale `model_provider` holen, sondern per `provider: ModelProvider = Depends(request_provider)`. Nur so greift der eigene Schlüssel der Nutzerin bzw. des Nutzers (`byok.py`, Header `X-LLM-*`). Im Frontend `...llmHeaders(llm)` nur bei diesen Endpunkten mitsenden.
- Neue Umgebungsvariablen in `main.py` lesen **und** in `.env.example`, `docker-compose.yml` und README dokumentieren.

## Frontend
In `apps/web/app/page.tsx` Fehler über `apiError(r)` (liest FastAPIs `detail`) werfen und bei Klick-Handlern
mit `guarded(setXError, async () => …)` kapseln – keine unbehandelten Promise-Rejections.

## Tests
`TestClient(app)` in `services/civic-core/tests/`; Erfolgs- und mindestens ein Fehlerpfad. Dann Skill `qualitaet-pruefen`.
