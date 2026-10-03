# Architecture

The civic core owns document analysis, evidence and civic reasoning. Channels only normalize transport. Source connectors only retrieve official material.

```text
Web / WhatsApp / OpenClaw
          ↓
      Civic Core
          ↓
Document → deterministic extraction → official-source resolution → evidence → answer
```

The model is never the source of truth. Exact legal references should bypass semantic search when an official resolver exists. Future retrieval: exact reference + BM25 + vector search + reranking + authority weighting.
