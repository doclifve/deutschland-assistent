# Architecture — v0.2

Deutschland Assistent separates document understanding, official-source retrieval and citizen-facing explanation.

Flow: Web/WhatsApp/OpenClaw → Civic Core → document parsing (basic or Docling OCR) → deterministic extraction (deadlines, laws, LeiKa, authority hints) → Evidence Engine → Gesetze im Internet + NeuRIS + official service/benefit sources → dedupe/ranking → structured answer.

## Core rule

**The model is not the source of truth.** Original citizen documents and official sources are. A future LLM may explain or translate evidence but must not silently replace it.

## Retrieval order

1. Exact legal references are resolved deterministically through Gesetze im Internet.
2. Exact LeiKa identifiers become direct Bundesportal links.
3. NeuRIS is searched for current federal legislation.
4. Curated official service/benefit sources are searched transparently.
5. Evidence is deduplicated and ranked with exact authoritative matches first.

NeuRIS is an official trial service with an incomplete dataset, so it is never the only fallback for an explicit legal citation.
