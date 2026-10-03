# Architecture — v0.2.2

Deutschland Assistent separates document understanding, official-source retrieval and citizen-facing explanation.

```text
Web / WhatsApp / OpenClaw
          ↓
      Civic Core
          ↓
PDF / photo / text
          ↓
Basic parser → Docling OCR fallback
          ↓
Deterministic extraction
(deadlines · requirements · appeal instructions · statutes · LeiKa · authority)
          ↓
Evidence Engine
          ↓
Gesetze im Internet · NeuRIS legislation · NeuRIS case law · official services
          ↓
Deduplication + evidence ranking
          ↓
Structured citizen answer
```

## Core rule

**The model is not the source of truth.** Original citizen documents and official sources are. A future LLM may explain or translate evidence but must not silently replace it.

## Document parsing

- Digital PDFs/text take the fast deterministic path first.
- Images and text-poor PDFs use local Docling OCR in `DOCUMENT_ENGINE=auto`.
- Docling remote services are disabled.
- Page count and upload size are capped.
- Production images can prefetch model artifacts into `DOCLING_ARTIFACTS_PATH`.
- Parsing runs in a thread pool so OCR does not block the async API loop.

## Retrieval order

1. Exact legal references resolve deterministically through Gesetze im Internet.
2. Exact LeiKa identifiers become direct Bundesportal links.
3. NeuRIS is searched for current federal legislation.
4. For legal/appeal queries, NeuRIS case law is searched separately and labeled as case law.
5. Curated official service/benefit sources are searched transparently.
6. Evidence is deduplicated and ranked with exact authoritative matches first.

NeuRIS is an official trial service with an incomplete dataset, so it is never the only fallback for an explicit legal citation.

## Privacy boundary

Uploaded document text lives in an ephemeral in-memory store with TTL, size cap and explicit DELETE endpoint. The WhatsApp adapter downloads media only long enough to pass it into the same document pipeline; WhatsApp itself remains an external channel and therefore is not equivalent to a local-only upload path.
