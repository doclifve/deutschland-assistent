---
name: agentenaktion
description: Bestätigungspflichtige Agentenaktionen des Deutschland Assistenten bauen oder ändern (Termine, PDF-Formulare, Briefe; ActionStore, /v1/actions/*, OpenClaw-Connector). Verwenden, wenn der Assistent etwas „für den Nutzer erledigen“ soll.
---
# Agentenaktion

Regel (CONTRIBUTING.md): Folgenreiche externe Aktionen brauchen **explizite menschliche Bestätigung**.

## Lebenszyklus
`prepared` → (Nutzer bestätigt `/v1/actions/{id}/confirm` mit `expected_version`) → `approved` | `cancelled`
→ intern ausgeführt (`completed`) oder externer Connector meldet über `/v1/actions/{id}/complete`
(Header `X-Agent-Token` = `AGENT_EXECUTION_TOKEN`) `completed` | `failed`.

## Bausteine
- `new_action(type, summary=…, payload=…, execution_target=…, ttl_seconds=…)` in `actions.py`; Typ muss in
  `AgentActionType` (schemas.py) stehen.
- Zustandswechsel **immer** mit `ACTION_STORE.update_action(id, neu, expected_version=alt.version)` und bei
  `False` mit 409 antworten – das ist der atomare Schutz gegen doppelte Bestätigung.
- Payload enthält nur, was der Nutzer in der Vorschau gesehen hat; nach Bestätigung nichts mehr hinzufügen.
- LLM darf nur Vorschläge machen (z. B. `map_profile_to_form`), nie Felder erfinden, Checkboxen setzen oder unterschreiben.
- Externe Ausführung (OpenClaw, `channels/openclaw/deutschland-assistent/SKILL.md`) nur bei Status `approved`.

## Tests
Muster in `tests/test_v030_agents.py`: Vorbereiten → Bestätigen → Status/Artefakt prüfen, plus Abbruch,
falsche Version (409), fehlender Token (503/401).
