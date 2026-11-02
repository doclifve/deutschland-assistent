---
name: amtliche-quelle-hinzufuegen
description: Neue amtliche Leistung, Behördenseite oder Termin-Anliegen in das Quellenregister des Deutschland Assistenten aufnehmen (services.de.json, appointments.de.json) oder einen neuen Evidenz-Connector anbinden. Verwenden bei „füge X hinzu“, „Quelle für Y fehlt“, neue Leistung/Behörde/Terminart.
---
# Amtliche Quelle hinzufügen

Grundsatz (SOURCE_POLICY.md): Nur amtliche, versionierte Quellen. Suchmaschinen-Snippets und Modellwissen sind keine Evidenz.

## Leistung im Register (`services/civic-core/deutschland_assistent/data/services.de.json`)
```json
{
  "title": "Wohngeld",
  "summary": "Ein Satz, neutral, ohne Rechtsfolge.",
  "url": "https://<amtliche Domain>/...",
  "authority": "Herausgebende Behörde",
  "keywords": ["wohngeld", "mietzuschuss", "wogg"]
}
```
- URL nur von Bund/Land/Kommune/Bundesagentur (z. B. `bund.de`, `arbeitsagentur.de`, `familienportal.de`). Erreichbarkeit prüfen.
- Keywords klein geschrieben, inklusive Abkürzungen und Gesetzeskürzel, wie Bürger sie schreiben.
- Keine Duplikate: vorher `grep -i` auf Titel/URL.

## Termin-Anliegen (`data/appointments.de.json`)
Felder wie bestehende Einträge (`id`, `title`, `office`, `keywords`, Unterlagen/Links). Keine erfundenen Öffnungszeiten, Gebühren oder Buchungs-URLs.

## Neuer Evidenz-Connector (`evidence.py`)
- Klasse mit `source_id`, liefert `EvidenceItem`s (Feld `kind` nur aus dem `Literal` in `schemas.py`).
- Herausgeber, Abrufdatum und Version/Gültigkeit in `metadata` ablegen.
- Fehler als `httpx.HTTPError`/`ValueError` werfen – `EvidenceEngine.collect` fängt diese und ergänzt eine Warnung; unerwartete Antwortformate per `_members()`-Muster ablehnen statt mit `AttributeError` abzustürzen.
- In `/v1/sources` (main.py) und `docs/DATA_SOURCES.md` eintragen.

## Test
In `tests/test_api.py`/`test_v02.py` eine Frage ergänzen, die die neue Quelle treffen muss; danach `make test-backend`.
