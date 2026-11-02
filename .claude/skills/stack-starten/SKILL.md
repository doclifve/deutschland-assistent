---
name: stack-starten
description: Deutschland Assistent lokal installieren, starten und im Browser prüfen (Civic Core API :8000, Next.js-Web :3000, optional WhatsApp-Adapter :8010). Verwenden, wenn die App laufen, angeschaut, gescreenshottet oder eine Änderung im echten Betrieb bestätigt werden soll.
---
# Stack starten

## Einmalig einrichten
```bash
make setup        # .env aus .env.example, Python-venv (services/civic-core/.venv), npm ci
```
Python ≥ 3.11, Node ≥ 20.9. Ohne Docker lauffähig; `make up` nutzt Docker Compose.

## Starten
- Entwicklung (Auto-Reload, beide Dienste): `make dev`
- Einzeln: `make dev-backend` (API :8000), `make dev-web` (Web :3000), `make dev-whatsapp` (:8010)
- Produktionsnah: `make build-web`, dann `cd apps/web && npx next start -p 3000`

Für Agenten-Sitzungen Dienste im Hintergrund starten (Logs in eine Datei umleiten) und warten, bis
`curl -sf localhost:8000/health` und `curl -sf localhost:3000` antworten.

## Prüfen
- API-Rauchtest: `curl -s -X POST localhost:8000/v1/ask -H 'content-type: application/json' -d '{"message":"Was bedeutet § 60 SGB I?","language":"de"}'`
- OpenAPI-Doku: http://localhost:8000/docs
- Browser-End-to-End (Playwright ist vorinstalliert, `require('playwright')`):
  `node .claude/skills/stack-starten/scripts/smoke.js` – stellt eine Frage, lädt ein Test-Formular hoch,
  speichert Screenshots nach `$SMOKE_OUT` (Standard: aktuelles Verzeichnis) und schlägt bei JS-Fehlern fehl.

## Hinweise
- Ohne `LLM_PROVIDER` läuft alles deterministisch; Chat und Formular-Agent melden dann sichtbar „LLM nicht konfiguriert“ – das ist erwartet.
- Die Rechtsinformationen-API (NeuRIS, Testphase) ist extern; fällt sie aus, erscheinen Warnungen, Antworten kommen trotzdem.
- `NEXT_PUBLIC_CIVIC_API_URL` wird zur Build-Zeit eingebacken – nach Änderung neu bauen.
- Dienste nach dem Test wieder beenden (`pkill -f "uvicorn deutschland_assistent"`, `pkill -f "next start"`).
