# Datenquellen — v0.2.4

## Gesetze im Internet

Deterministischer Fallback für explizite Bundesgesetz-Zitate mit direkten Links auf die amtliche Fassung.

## Rechtsinformationen des Bundes / NeuRIS

Basis:

`https://testphase.rechtsinformationen.bund.de`

Der Evidence-Layer nutzt die offizielle API für:

- `GET /v1/legislation` – Bundesrecht
- `GET /v1/case-law` – Rechtsprechung
- `GET /v1/case-law/{documentNumber}` – vollständige Entscheidungs-Metadaten und Textfelder
- `GET /v1/case-law/{documentNumber}.html` – HTML-Darstellung
- `GET /v1/case-law/{documentNumber}.xml` – XML/LegalDocML-orientierte Darstellung

### Suchfunktionen

Der Connector unterstützt:

- Volltextsuche über `searchTerm`
- exakte Phrasensuche durch Anführungszeichen
- Pagination über `pageIndex`
- Datumsfilter für Rechtsprechung über `dateFrom` / `dateTo`
- Gültigkeitsfilter für Gesetzgebung über `temporalCoverageFrom` / `temporalCoverageTo`

Gesetzgebung wird standardmäßig auf den aktuellen Tag gefiltert, damit möglichst die aktuell geltende Fassung gefunden wird.

### ELI und ECLI

Wo vorhanden, speichert der Connector:

- **ELI** für Gesetzgebung
- **ECLI** für Rechtsprechung
- Dokumentnummer
- Gericht
- Entscheidungsdatum
- Dokumenttyp
- direkte JSON-, HTML- und XML-URLs

Diese Identifier sollen später als stabile Knoten im Civic Knowledge Graph dienen.

### Detail-Enrichment

Für die wichtigsten Rechtsprechungstreffer kann der Evidence-Layer den vollständigen JSON-Endpunkt abrufen. Bevorzugte Felder für die evidenzgebundene Erklärung sind insbesondere:

- Leitsatz
- Orientierungssatz
- Überschrift
- Tenor
- Entscheidungsgründe
- Gründe
- Tatbestand

Such-Snippets werden dadurch, wenn verfügbar, durch kompaktere amtliche Detailinhalte ersetzt.

### Robustheit

Der Connector enthält:

- kurzen In-Memory-TTL-Cache
- Retry bei HTTP 429 und 5xx
- exponentielles Backoff
- konfigurierbare Timeouts
- begrenzte Zahl von Detailabrufen

Konfiguration:

```text
NEURIS_BASE_URL
NEURIS_TIMEOUT_SECONDS
NEURIS_CACHE_TTL_SECONDS
NEURIS_MAX_RETRIES
NEURIS_ENRICH_CASE_LAW
```

Zusätzlich läuft ein täglicher GitHub-Actions-Smoke-Test gegen Gesetzgebung und Rechtsprechung, um API-Ausfälle oder Schemaänderungen früh zu erkennen.

### Einschränkung

Die Rechtsinformationen des Bundes befinden sich weiterhin in der Testphase und der Datenbestand kann unvollständig sein. Explizite Normzitate behalten deshalb den direkten Fallback auf **Gesetze im Internet**. Rechtsprechung wird als eigene Evidenzart behandelt und nicht mit Gesetzesnormen gleichgesetzt.

## Bundesportal / LeiKa

Exakte LeiKa-Identifier werden direkt auf amtliche Bundesportal-Leistungsseiten verlinkt. Das Projekt erfindet keine nicht dokumentierte Bundesportal-API.

## Amtliche Leistungen

Ein nachvollziehbares JSON-Register verweist auf amtliche Seiten unter anderem von:

- Bundesagentur für Arbeit / Familienkasse
- Familienportal
- Deutsche Rentenversicherung
- Bundesministerium für Gesundheit
- Bundesportal

## Docling

Docling ist die lokale OCR-/Layout-Engine für Fotos, Scans und textarme PDFs. Das Produktions-Image installiert die Docling-Erweiterung. Im Modus `DOCUMENT_ENGINE=auto` läuft zuerst die schnelle deterministische Verarbeitung; Docling wird nur bei OCR-Bedarf aktiviert. Entfernte Docling-Dienste sind deaktiviert.
