# Data Sources — v0.2

## Gesetze im Internet
Deterministic fallback for explicit federal-law citations, with direct section links.

## Rechtsinformationen des Bundes / NeuRIS
Base: https://testphase.rechtsinformationen.bund.de
v0.2 uses GET /v1/legislation with searchTerm and current-day temporalCoverage filters. The service is official, open and still in test phase; its dataset is incomplete.

## Bundesportal / LeiKa
Exact LeiKa identifiers are linked directly to official Bundesportal service pages. v0.2 deliberately does not invent an undocumented Bundesportal API.

## Official benefits/services
An auditable JSON registry currently points to official pages from Bundesagentur für Arbeit/Familienkasse, Familienportal, Deutsche Rentenversicherung, BMG and Bundesportal.

## Docling
Optional OCR/layout-aware parsing for scans and images. Install with pip install -e '.[docling]'. In DOCUMENT_ENGINE=auto mode, fast deterministic parsing runs first and Docling is attempted for images or text-poor PDFs.
