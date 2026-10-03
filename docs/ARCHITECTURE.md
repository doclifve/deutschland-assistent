# Architektur — v0.2.3
# Architektur — v0.2.4

Deutschland Assistent trennt Dokumentverständnis, amtliche Recherche und sprachliche Erklärung strikt voneinander.

```text
Web / WhatsApp / OpenClaw
          ↓
      Civic Core
          ↓
PDF / Foto / Text
          ↓
Basic Parser → Docling-OCR-Fallback
          ↓
deterministische Extraktion
(Fristen · Anforderungen · Rechtsbehelf · Normen · LeiKa · Behörde)
          ↓
Evidence Engine
          ↓
Gesetze im Internet · NeuRIS Gesetzgebung · NeuRIS Rechtsprechung · amtliche Leistungen
Gesetze im Internet · Rechtsinformationen des Bundes · amtliche Leistungen
          ↓
Deduplizierung + Evidence Ranking
          ↓
strukturierter Evidence Context
          ↓
┌───────────────────────────┬────────────────────────────┐
│ deterministischer Fallback│ optionale LLM-Erklärung   │
│                           │ Germany-hosted / Provider  │
└───────────────────────────┴────────────────────────────┘
          ↓
evidenzbeschränkte Bürgerantwort
```

## Kernregel

**Das Modell ist nicht die Quelle der Wahrheit.** Maßgeblich sind Originaldokumente und amtliche Quellen.

Das Sprachmodell sitzt hinter der Evidence Engine. Es darf vorhandene Evidenz verständlicher formulieren, aber keine zusätzliche rechtliche Wahrheit erzeugen.

## LLM Provider Layer

Der Core unterstützt:

- `disabled` – Standard; kein Sprachmodell nötig.
- `germany_hosted` – OpenAI-kompatibler Endpunkt mit technischer Sperre `LLM_REGION=DE`.
- `openai_compatible` – generischer kompatibler Endpunkt.
- `ollama` – lokaler/selbst betriebener kompatibler Endpunkt.

Die Provider-Schicht ist absichtlich klein. Fachlogik, Fristen, Quellenranking und Rechtsverweise bleiben außerhalb des Modells.

### Minimierter Kontext

Standardmäßig wird nicht der vollständige Dokumenttext an das LLM gesendet. Der Prompt enthält strukturierte Evidenzobjekte wie:

- erkannter Dokumenttyp
- Behörde
- erkannte Fristen
- Anforderungen
- Rechtsbehelf
- im Dokument genannte Rechtsnormen
- Treffer aus amtlichen Quellen

### Claim-Gating

Das Modell muss strukturierte Claims mit Evidence-IDs zurückgeben.

```text
LLM Claim
   ↓
bekannte Evidence-ID?
   ├─ nein → verwerfen
   └─ ja
       ↓
neues Datum / neuer Paragraph?
   ├─ nicht in referenzierter Evidenz → verwerfen
   └─ belegt → ausgeben
```

```

## Kernregel

**Das Modell ist nicht die Quelle der Wahrheit.** Maßgeblich sind Originaldokumente und amtliche Quellen.

Das Sprachmodell sitzt hinter der Evidence Engine. Es darf vorhandene Evidenz verständlicher formulieren, aber keine zusätzliche rechtliche Wahrheit erzeugen.

## LLM Provider Layer

Der Core unterstützt:

- `disabled` – Standard; kein Sprachmodell nötig.
- `germany_hosted` – OpenAI-kompatibler Endpunkt mit technischer Sperre `LLM_REGION=DE`.
- `openai_compatible` – generischer kompatibler Endpunkt.
- `ollama` – lokaler/selbst betriebener kompatibler Endpunkt.

Die Provider-Schicht ist absichtlich klein. Fachlogik, Fristen, Quellenranking und Rechtsverweise bleiben außerhalb des Modells.

### Minimierter Kontext

Standardmäßig wird nicht der vollständige Dokumenttext an das LLM gesendet. Der Prompt enthält strukturierte Evidenzobjekte wie:

- erkannter Dokumenttyp
- Behörde
- erkannte Fristen
- Anforderungen
- Rechtsbehelf
- im Dokument genannte Rechtsnormen
- Treffer aus amtlichen Quellen

### Claim-Gating

Das Modell muss strukturierte Claims mit Evidence-IDs zurückgeben.

```text
LLM Claim
   ↓
bekannte Evidence-ID?
   ├─ nein → verwerfen
   └─ ja
       ↓
neues Datum / neuer Paragraph?
   ├─ nicht in referenzierter Evidenz → verwerfen
   └─ belegt → ausgeben
```

Das ist noch kein vollständiger semantischer Wahrheitsbeweis. Der v0.2.3-Benchmark muss deshalb ausdrücklich die **Unsupported Claim Rate** messen.

### Prompt-Injection

Dokumenttext und Quellen-Snippets werden als Daten behandelt, niemals als Instruktionen. Das Systemprompt weist das Modell ausdrücklich an, eingebettete Anweisungen in Briefen oder Snippets zu ignorieren.

## Dokumentverarbeitung

- Digitale PDFs und Textdateien nehmen zuerst den schnellen deterministischen Pfad.
- Bilder und textarme PDFs verwenden im `DOCUMENT_ENGINE=auto` lokales Docling-OCR.
- Remote-Dienste von Docling sind deaktiviert.
- Seitenzahl und Uploadgröße sind begrenzt.
- Modellartefakte können in `DOCLING_ARTIFACTS_PATH` vorab geladen werden.
- OCR läuft im Threadpool und blockiert den Async-API-Loop nicht.

## Retrieval-Reihenfolge

1. Exakte Gesetzeszitate werden deterministisch über Gesetze im Internet aufgelöst.
2. Exakte LeiKa-IDs werden zu direkten Bundesportal-Links.
3. NeuRIS wird nach aktuellem Bundesrecht durchsucht.
4. Bei juristischen Fragen/Rechtsbehelfen wird Rechtsprechung separat gesucht und als solche markiert.
5. Kuratierte amtliche Leistungsquellen werden transparent durchsucht.
6. Evidenz wird dedupliziert und gerankt; exakte amtliche Treffer stehen vorn.

NeuRIS ist ein offizieller Testdienst mit unvollständigem Datenbestand und bleibt deshalb bei expliziten Normzitaten nicht der einzige Fallback.

1. Exakte Gesetzeszitate werden deterministisch über Gesetze im Internet aufgelöst.
2. Exakte LeiKa-IDs werden zu direkten Bundesportal-Links.
3. Die Rechtsinformationen des Bundes werden nach aktuell geltender Bundesgesetzgebung durchsucht.
4. Bei juristischen Fragen/Rechtsbehelfen wird Rechtsprechung separat gesucht und als solche markiert.
5. Für die wichtigsten Rechtsprechungstreffer kann der vollständige amtliche Detail-Endpunkt geladen werden.
6. ELI, ECLI, Dokumentnummer, Gericht und Entscheidungsdatum werden als strukturierte Metadaten weitergegeben.
7. Kuratierte amtliche Leistungsquellen werden transparent durchsucht.
8. Evidenz wird dedupliziert und gerankt; exakte amtliche Treffer stehen vorn.

Die Rechtsinformationen des Bundes befinden sich in der Testphase und bleiben deshalb bei expliziten Normzitaten nicht der einzige Fallback.

## Schutz der amtlichen Schnittstelle

Der Connector verwendet einen kurzen TTL-Cache und wiederholt nur temporär fehlgeschlagene Aufrufe (HTTP 429 bzw. 5xx) mit Backoff. Dadurch werden unnötige Wiederholungsanfragen vermieden.

Ein täglicher GitHub-Actions-Smoke-Test prüft die Collection-Endpunkte für Gesetzgebung und Rechtsprechung. Ein Schema- oder Verfügbarkeitsproblem wird damit unabhängig vom Nutzerverkehr sichtbar.

## Datenschutzgrenze

Hochgeladene Dokumente liegen derzeit in einem flüchtigen In-Memory-Store mit TTL, Größenlimit und explizitem DELETE-Endpunkt.

Die LLM-Schicht ist optional. Bei externer Inferenz muss der Betreiber zusätzlich prüfen:

- tatsächlicher Hosting- und Verarbeitungsort
- Auftragsverarbeitung
- Unterauftragsverarbeiter
- Prompt-/Response-Logging
- Retention
- Trainingsnutzung
- Transportverschlüsselung

`LLM_REGION=DE` erzwingt eine Konfigurationsabsicht, beweist aber nicht die physische Datenresidenz.

WhatsApp bleibt ein externer Kommunikationskanal und ist datenschutztechnisch nicht gleichbedeutend mit lokalem Web-Upload.
