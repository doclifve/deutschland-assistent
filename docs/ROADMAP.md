# Roadmap

## v0.2.2 – Dokumentverständnis ✅

- [x] PDF-/Text-Verarbeitung
- [x] Docling-OCR für Fotos, Scans und textarme PDFs
- [x] explizite und relative Fristen
- [x] Rechtsverweise und LeiKa-Erkennung
- [x] Anforderungen wie Unterlagen, Angaben, Zahlungen und Handlungen
- [x] Rechtsbehelfsbelehrungen
- [x] Gesetze-im-Internet-Resolver
- [x] NeuRIS-Gesetzgebung
- [x] NeuRIS-Rechtsprechung
- [x] Bundesportal-/Leistungsquellen
- [x] Evidence Ranking
- [x] Weboberfläche
- [x] WhatsApp-Cloud-Adapter
- [x] temporäre Dokumentablage mit TTL und Lösch-Endpunkt

## v0.2.3 – Behördenbrief-Benchmark + Erklärungsschicht

- [x] austauschbare Model-Provider-Schnittstelle
- [x] optionaler Germany-hosted OpenAI-kompatibler Provider
- [x] deterministischer Fallback ohne LLM
- [x] minimierter Evidence Context statt vollständigem Brief
- [x] Claims müssen bekannte Evidence-IDs referenzieren
- [x] Guard gegen unbelegte neue Datums-/Paragraphenangaben
- [x] Prompt-Injection-Regel für Dokument- und Quelleninhalte
- [ ] Provider-Vertrags-/Datenschutz-Checkliste für Produktion

- [ ] Ground-Truth-Schema
- [ ] 200–500 synthetische/anonymisierte Behördenbriefe
- [ ] OCR Success Rate
- [ ] Deadline Precision / Recall
- [ ] Requirement Extraction F1
- [ ] Appeal Detection Accuracy
- [ ] Legal Citation Accuracy
- [ ] Source Retrieval Recall@5
- [ ] Unsupported Claim Rate
- [ ] Critical Deadline Error Rate
- [ ] Benchmark-Report in CI

## v0.2.4 – Evidence Engine 2.0

- [x] vertiefter Connector für die Rechtsinformationen des Bundes
- [x] Volltext- und exakte Phrasensuche
- [x] Datumsfilter für Rechtsprechung
- [x] Gültigkeitsfilter für Gesetzgebung
- [x] Pagination
- [x] ELI-/ECLI-Metadaten
- [x] vollständiger JSON-Abruf einzelner Entscheidungen
- [x] direkte JSON-/HTML-/XML-Links für Rechtsprechung
- [x] Detail-Enrichment der wichtigsten Rechtsprechungstreffer
- [x] TTL-Cache
- [x] Retry/Backoff bei 429 und 5xx
- [x] täglicher API-Smoke-Test
- [ ] einheitliches Source-Registry-Schema
- [ ] robustere Relevanzbewertung
- [ ] breitere Bundesportal-/LeiKa-Abdeckung
- [ ] weitere amtliche Leistungsquellen
- [ ] erste Civic-Knowledge-Graph-Strukturen
- [ ] klare Versions- und Gültigkeitsinformationen pro Quelle

## v0.3 – Bürger-Workflows

- [x] freier LLM-Chat mit Gesprächsverlauf
- [x] amtliche Evidenz bei Bürger-/Rechtsfragen
- [x] Terminaktionen: Prepare → Preview → Confirm → External Execute
- [x] geschützter Rückkanal für externe Buchungsagenten
- [x] ausfüllbare PDF-Formulare erkennen
- [x] LLM-gestützte Zuordnung von Profildaten zu Formularfeldern
- [x] PDF erst nach Bestätigung erzeugen
- [x] optimistische Versionsprüfung gegen veraltete Bestätigungen
- [ ] erste produktive Termin-Connectoren für konkrete Behördenportale

- [ ] Jobcenter-Workflow
- [ ] Familienleistungen
- [ ] Kranken-/Pflegeversicherung
- [ ] Rentenversicherung
- [ ] Finanzamt
- [ ] Checklisten
- [ ] Antwortentwürfe
- [ ] Erinnerungen
- [ ] Human Approval vor externen Aktionen

## v0.4 – Sprache und Barrierefreiheit

- [ ] Einfache Sprache
- [ ] Englisch
- [ ] Türkisch
- [ ] Arabisch
- [ ] Ukrainisch
- [ ] Russisch
- [ ] Dari/Persisch
- [ ] Voice
- [ ] Accessibility-/WCAG-Tests

## v0.5 – Produktionshärtung

- [ ] Rate Limiting
- [ ] dauerhafte Job Queue
- [ ] Redis / PostgreSQL
- [ ] verschlüsselte temporäre Ablage
- [ ] PII-Redaction
- [ ] Observability
- [ ] Audit Logs
- [ ] Backup-/Recovery-Konzept
- [ ] Source-Monitoring

## v1.0 – offene Bürger-Infrastruktur

- [ ] öffentlicher reproduzierbarer Benchmark
- [ ] belastbare Qualitätsgrenzen
- [ ] mehrere vollständig getestete Behördenworkflows
- [ ] dokumentierte Governance
- [ ] Self-Hosting
- [ ] externe Contributors
- [ ] Datenschutz- und Sicherheitsreview
- [ ] stabile öffentliche Schnittstellen

Die ausführliche Planung steht in [PROJEKTPLAN.md](PROJEKTPLAN.md).
