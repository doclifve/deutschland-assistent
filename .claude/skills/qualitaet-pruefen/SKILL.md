---
name: qualitaet-pruefen
description: Alle Prüfungen des Deutschland Assistenten ausführen, die auch die CI macht (Ruff, pytest für Civic Core und WhatsApp-Adapter, TypeScript, Next.js-Build), und Fehler beheben. Vor jedem Commit/Push und nach Änderungen an Python- oder Web-Code verwenden.
---
# Qualität prüfen

```bash
make check          # = make lint test build-web
make typecheck      # nur TypeScript (schnell)
make test-backend   # nur Civic Core
```
Voraussetzung: `make setup` lief einmal.

## Vorgehen bei Fehlern
1. Fehlenden Test zuerst reproduzieren (`cd services/civic-core && .venv/bin/python -m pytest -q tests/<datei>.py -k <name>`).
2. Ursache beheben, nicht den Test abschwächen. Tests nie überspringen oder löschen, um grün zu werden.
3. Für jeden behobenen Bug einen Regressionstest ergänzen (Backend: `services/civic-core/tests/`,
   WhatsApp: `channels/whatsapp-cloud/tests/`). PDF-Testformulare liefert `tests/make_form.py`.
4. Netzwerkzugriffe in Tests immer mit `httpx.MockTransport` simulieren – nie echte APIs aufrufen.

## Was die CI zusätzlich erwartet
- `apps/web/package-lock.json` bleibt synchron zu `package.json` (`npm install --package-lock-only`).
- `next build` darf keine getrackten Dateien verändern (`git status` danach sauber).
- Optionale, tiefere Typprüfung: `.venv/bin/pip install pyright && .venv/bin/pyright deutschland_assistent`
  (meldet bekannte Rauschen bei `**dict`-Kwargs; nur neue Fehler beachten).
