---
name: extraktion-erweitern
description: Deterministische Erkennung in Behördenschreiben erweitern oder korrigieren – Fristen, relative Fristen, Gesetzeszitate, Rechtsbehelfsbelehrungen, angeforderte Unterlagen, Zahlungen, Dokumenttyp (extraction.py). Verwenden, wenn ein Brief falsch oder unvollständig ausgewertet wird.
---
# Extraktion erweitern

Datei: `services/civic-core/deutschland_assistent/extraction.py`. Rückgabetypen in `schemas.py`.
Die Extraktion ist die Wahrheitsschicht – das LLM darf nur erklären (MODEL_POLICY.md).

## Vorgehen
1. **Beispieltext als Test zuerst** (anonymisiert, keine echten Bürgerdaten!) in
   `tests/test_v021.py` bzw. `tests/test_relative_deadlines.py` – Test muss vorher rot sein.
2. Regex/Logik minimal erweitern. Bestehende Konstanten wiederverwenden (`DATE_RE`, `RELATIVE_RE`,
   `LEGAL_REF`, `APPEAL_*`, `REQUIREMENT_HEADING`).
3. Unsicherheit sichtbar machen: geschätzte Daten mit `confidence="low"`, nie stillschweigend raten.
4. Fristberechnung juristisch konservativ (§§ 187 ff. BGB, § 193 BGB → `next_weekday`; Monatsende über `add_months`).
5. Neue Literal-Werte (z. B. Rechtsbehelfsart) in `schemas.py` ergänzen **und** im Frontend
   (`apps/web/app/page.tsx`) sowie im WhatsApp-Format (`channels/whatsapp-cloud/app.py: format_answer`) berücksichtigen.
6. `make test` und `make lint`.

## Fallstricke
- Deutsche Datumsformate: `1.2.2026`, `01.02.2026`, `1. Februar 2026`.
- Gesetzeszitate: `§ 60 Abs. 1 SGB I`, `§§ 66, 67 SGB I`, `Art. 3 GG` – URL-Bau über `law_url`.
- Kein Regex mit katastrophalem Backtracking auf ganzen Dokumenten (bis 30 Seiten); Quantoren begrenzen (`{3,180}`).
