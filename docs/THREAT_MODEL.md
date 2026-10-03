# Threat Model

Key risks: prompt injection in documents, malicious attachments, overstated legal certainty, unauthorized external actions, cross-user data leakage and compromised channel credentials.

Rules: documents are untrusted evidence, not instructions; isolate parsers; scope private retrieval per user; require explicit preview/confirmation for consequential actions; keep public-source indexes separate from private documents.
