# Deutschland Assistent – Hinweise für Claude

Open-Source-Bürgerassistent: Behördenpost, Gesetze und Leistungen verständlich machen – **evidenzbasiert**.
Grundprinzip: Das Modell ist nicht die Quelle der Wahrheit; maßgeblich sind Originaldokument und amtliche Quellen
(`MODEL_POLICY.md`, `SOURCE_POLICY.md`). Sprache von Code-Kommentaren/Doku: überwiegend Deutsch, UI-Texte immer Deutsch.

## Aufbau
- `services/civic-core/` – FastAPI-Kern (Python ≥ 3.11). `deutschland_assistent/main.py` = alle Endpunkte;
  `extraction.py` (deterministische Fristen/Zitate/Rechtsbehelfe), `evidence.py` (Gesetze im Internet, NeuRIS,
  Leistungsregister), `answer_generation.py`/`chat.py`/`model_provider.py` (optionales LLM, OpenAI-kompatibel),
  `actions.py`/`forms.py`/`appointments.py`/`letters.py` (bestätigungspflichtige Agenten), `data/*.json` (Register).
- `apps/web/` – Next.js 16 / React 19, eine Seite `app/page.tsx`.
- `channels/whatsapp-cloud/` – WhatsApp-Cloud-API-Adapter (FastAPI), `channels/openclaw/` – OpenClaw-Skill.
- `docs/` – Architektur, Bedrohungsmodell, Datenquellen, Roadmap.

## Befehle
`make setup` · `make dev` · `make check` (Lint + Tests + Web-Build, wie CI) · `make help`.
venv liegt in `services/civic-core/.venv`.

## Regeln
- Muss mit `LLM_PROVIDER=disabled` vollständig funktionieren; LLM-Fehler → deterministischer Fallback.
- Keine echten Bürgerdokumente, Secrets oder personenbezogene Daten committen; Testdaten synthetisch.
- Folgenreiche Aktionen nur nach expliziter Bestätigung (Versionierte Actions, Compare-and-Swap).
- Tests nie mit echten Netzwerkaufrufen – `httpx.MockTransport` nutzen.
- Jeder Bugfix bekommt einen Regressionstest.

## Projekt-Skills (`.claude/skills/`)
`stack-starten`, `qualitaet-pruefen`, `amtliche-quelle-hinzufuegen`, `extraktion-erweitern`, `api-endpunkt`, `agentenaktion`.
