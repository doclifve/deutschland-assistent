# Roadmap

## v0.2 — Evidence Engine
- [x] deterministic PDF/text parsing
- [x] deadline, law, LeiKa and authority extraction
- [x] Gesetze-im-Internet exact resolver
- [x] official NeuRIS legislation search
- [x] Bundesportal/LeiKa direct linking
- [x] curated official benefits/services catalog
- [x] evidence deduplication and ranking
- [x] /v1/evidence/search and /v1/sources
- [x] relative deadline hardening + ephemeral document store

## v0.2.2 — Document Intelligence
- [x] production container installs Docling OCR
- [x] photo/scan and text-poor-PDF OCR path
- [x] local-only Docling configuration + model cache/prefetch hook
- [x] structured extraction of requested documents/actions/payments
- [x] structured Rechtsbehelfsbelehrung extraction
- [x] NeuRIS case-law connector
- [x] case-law evidence shown separately from statutes
- [x] WhatsApp image/document ingestion
- [x] Meta webhook signature verification
- [x] document expiry + explicit DELETE
- [x] 28 deterministic/API connector tests

## v0.2.x hardening
- [ ] photographed-letter OCR benchmark with diverse real-world layouts (de-identified/synthetic)
- [ ] OCR confidence/quality gates and retry strategy
- [ ] court/decision relevance benchmark
- [ ] nightly official-source freshness/smoke checks
- [ ] rate limiting and durable WhatsApp job queue
- [ ] optional evidence-constrained explanation model

## v0.3
- [ ] reminders, forms and guided workflows
- [ ] multilingual/voice rendering
- [ ] human-confirmed external actions
- [ ] privacy-preserving persistent user workspace
