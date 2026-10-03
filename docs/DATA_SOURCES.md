# Data Sources — v0.2.2

## Gesetze im Internet
Deterministic fallback for explicit federal-law citations, with direct section links.

## Rechtsinformationen des Bundes / NeuRIS
Base: https://testphase.rechtsinformationen.bund.de

The Evidence Engine uses:
- `GET /v1/legislation` for current federal legislation,
- `GET /v1/case-law` for federal case law.

NeuRIS is official and open, but remains in test phase and its dataset is incomplete. Exact statute citations therefore keep a direct Gesetze-im-Internet fallback. Case-law results are labeled separately and ranked below exact statutory citations.

## Bundesportal / LeiKa
Exact LeiKa identifiers are linked directly to official Bundesportal service pages. The project deliberately does not invent an undocumented Bundesportal API.

## Official benefits/services
An auditable JSON registry points to official pages from Bundesagentur für Arbeit/Familienkasse, Familienportal, Deutsche Rentenversicherung, BMG and Bundesportal.

## Docling
Docling is the local OCR/layout engine for photos, scans and text-poor PDFs. The production container installs the Docling extra. In `DOCUMENT_ENGINE=auto`, fast deterministic parsing runs first and Docling is invoked only when OCR is needed. Remote Docling services are disabled.
