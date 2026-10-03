# Projektplan – Deutschland Assistent

## Zielbild

Deutschland Assistent soll eine offene, gemeinwohlorientierte Zugangsschicht zu deutscher Verwaltung werden.

Der Leitstern ist ein klarer Bürger-Workflow:

    Behördenbrief fotografieren
            ↓
    Dokument verstehen
            ↓
    Fristen und Anforderungen erkennen
            ↓
    amtliche Quellen zuordnen
            ↓
    verständlich erklären
            ↓
    nächste Schritte vorbereiten

Der Assistent ersetzt weder Behörden noch Rechtsberatung. Er soll Menschen dabei helfen, amtliche Informationen zu finden, zu verstehen und strukturiert zu handeln.

## Entwicklungsprinzipien

1. **Evidence first** – Originaldokument und amtliche Quellen stehen über Modellwissen.
2. **Messbare Qualität vor Feature-Menge** – jede wichtige Fähigkeit soll evaluiert werden.
3. **Unsicherheit sichtbar machen** – geschätzte Fristen, OCR-Unsicherheit und semantische Treffer werden klar gekennzeichnet.
4. **Bürger-UX statt Entwickler-UX** – keine Modellnamen, Temperaturen oder internen Agentenbegriffe im öffentlichen Produkt.
5. **Privacy by default** – Dokumente nur so lange speichern wie nötig.
6. **Human Approval** – vorbereiten → Vorschau → Bestätigung → ausführen.
7. **Offene Infrastruktur** – Standards, Datenmodelle, Evaluationen und Connectoren bleiben nachvollziehbar.

# Phase 1 – v0.2.3: Behördenbrief-Benchmark

## Ziel

Nicht nur zeigen, dass das System funktioniert, sondern messen, wie zuverlässig es funktioniert.

## Datensatz

Zunächst 200–500 synthetische oder vollständig anonymisierte Schreiben aus Bereichen wie:

- Jobcenter
- Finanzamt
- Familienkasse
- Krankenkasse
- Pflegekasse
- Deutsche Rentenversicherung
- Wohngeldstelle
- BAföG
- Ausländerbehörde
- Bürgeramt
- Sozialamt

Keine echten personenbezogenen Bürgerdokumente in das öffentliche Repository aufnehmen.

## Ground Truth pro Dokument

    Dokumenttyp
    Behörde
    Schreibendatum
    Aktenzeichen
    explizite Frist
    relative Frist
    angeforderte Unterlagen
    angeforderte Angaben
    Zahlungsforderung
    sonstige Handlung
    Rechtsbehelf
    Rechtsgrundlagen
    LeiKa-/Leistungsbezug

## Kernmetriken

- OCR Success Rate
- Deadline Precision / Recall
- Requirement Extraction Precision / Recall / F1
- Appeal Detection Accuracy
- Legal Citation Accuracy
- Authority Recognition Accuracy
- Source Retrieval Recall@5
- Unsupported Claim Rate
- Hallucination Rate
- **Critical Deadline Error Rate**

### Kritische Fristenfehler

Ein Fristenfehler ist kritisch, wenn das System eine nicht im Dokument oder aus einer belastbaren Regel ableitbare Frist mit zu hoher Sicherheit ausgibt oder eine vorhandene relevante Frist übersieht.

## Repository-Struktur

    datasets/
      synthetic/
      schemas/
    evals/
      fixtures/
      metrics/
      runners/
    benchmark/
      reports/

## Definition of Done

- mindestens 200 Testdokumente
- maschinenlesbare Ground Truth
- reproduzierbarer Benchmark-Befehl
- JSON- und Markdown-Report
- CI-Check für Regressionen
- dokumentierte Baseline-Metriken

# Phase 2 – v0.2.4: Evidence Engine 2.0

## Ziel

Die Wissensschicht soll amtliche Informationen nicht nur finden, sondern sauber normalisieren, versionieren und miteinander verbinden.

## Priorisierte Quellen

1. Gesetze im Internet
2. NeuRIS – Gesetzgebung
3. NeuRIS – Rechtsprechung
4. Bundesportal / LeiKa
5. Bundesagentur für Arbeit / Familienkasse
6. Deutsche Rentenversicherung
7. Bundesministerium für Gesundheit
8. amtliche Länder- und Kommunalquellen

## Einheitliches Evidenzschema

Beispiel:

    {
      "claim": "Im Schreiben wird eine Mitwirkung verlangt.",
      "evidence": [
        {
          "source": "SGB I",
          "section": "§ 60",
          "authority": "Bund",
          "url": "...",
          "valid_from": "...",
          "retrieved_at": "...",
          "confidence": "high"
        }
      ]
    }

## Source Registry

Jede Quelle soll mindestens enthalten:

    source_id
    authority
    jurisdiction
    source_type
    canonical_url
    valid_from
    valid_until
    last_checked
    document_version
    license_or_terms

## Automatische Source-Checks

Regelmäßiger Job:

    Quelle erreichbar?
    Schema unverändert?
    amtlicher Link gültig?
    Version aktualisiert?
    Abruf erfolgreich?

## Civic Knowledge Graph

Langfristig sollen Beziehungen explizit modelliert werden:

    § 60 SGB I
       ├── Mitwirkungspflicht
       ├── typische Behördenanforderungen
       ├── betroffene Leistungen
       └── einschlägige Rechtsprechung

    Wohngeld
       ├── WoGG
       ├── LeiKa-Leistung
       ├── zuständige Stelle
       └── Antrags-/Nachweisprozesse

# Phase 3 – v0.3: Von „Verstehen“ zu „Handeln“

## Ziel

Aus einer Erklärung wird ein geführter Bürger-Workflow.

Beispiel:

    Jobcenter fordert:
    - Kontoauszüge
    - Mietvertrag

    Frist:
    21.10.2026

    Ihre nächsten Schritte:
    ☐ Kontoauszüge zusammenstellen
    ☐ Mietvertrag hinzufügen
    ☐ Antwort prüfen
    ☐ rechtzeitig übermitteln

## Funktionen

- Checklisten aus Schreiben erzeugen
- Antwortentwürfe vorbereiten
- Fristen als Erinnerung vormerken
- fehlende Unterlagen erklären
- zuständige Stelle anzeigen
- Widerspruch oder Einspruch als Entwurf vorbereiten
- Formulare vorbefüllen, sofern technisch und rechtlich sinnvoll

## Sicherheitsmodell

    Prepare
       ↓
    Preview
       ↓
    Human Approval
       ↓
    Execute

Keine rechtlich relevante Erklärung wird ohne ausdrückliche Nutzerfreigabe versendet oder eingereicht.

## Erste fünf hochwertige Workflows

### 1. Jobcenter / Grundsicherung
- Mitwirkungsaufforderung
- Bewilligungsbescheid
- Ablehnungsbescheid
- Rückforderung
- Widerspruch

### 2. Familienleistungen
- Kindergeld
- Kinderzuschlag
- Elterngeld

### 3. Kranken- und Pflegeversicherung
- Pflegegrad
- Kostenübernahme
- Ablehnung
- Widerspruch

### 4. Deutsche Rentenversicherung
- Rentenbescheid
- Versicherungsverlauf
- Erwerbsminderung

### 5. Finanzamt
- Steuerbescheid
- Nachforderung
- Frist
- Einspruch

# Phase 4 – v0.4: Sprache, Einfache Sprache und Barrierefreiheit

## Drei Verständlichkeitsstufen

    Originalinhalt
         ↓
    normales Deutsch
         ↓
    Einfache Sprache

## Zielsprachen

- Deutsch
- Englisch
- Türkisch
- Arabisch
- Ukrainisch
- Russisch
- Dari / Persisch

Die Rechtsrecherche bleibt auf den amtlichen deutschen Originalquellen aufgebaut.

## Accessibility

- Tastaturnavigation
- Screenreader-Unterstützung
- hohe Kontraste
- reduzierte Bewegung
- verständliche Fehlermeldungen
- WCAG-orientierte Tests
- Spracheingabe und Vorlesen als optionale Kanäle

# Phase 5 – v0.5: Produktionshärtung

## Infrastruktur

- Rate Limiting
- Job Queue
- Redis
- PostgreSQL
- verschlüsselte temporäre Dokumentablage
- PII-Redaction vor externen Modellen
- EU-/Deutschland-Hosting, wo sinnvoll
- OpenTelemetry
- Fehlertracking
- Audit Logs
- Backup-/Recovery-Konzept
- reproduzierbare Deployments
- Secret Management

## Datenschutz

Standardpfad:

    Upload
      ↓
    OCR
      ↓
    Analyse
      ↓
    Antwort
      ↓
    automatische Löschung

Längere Speicherung nur mit transparenter Zustimmung.

# Phase 6 – Open-Source-Community

## Ziel

Das Projekt soll nicht von einer einzelnen Person abhängig bleiben.

## GitHub-Struktur

Weiter ausbauen:

- CONTRIBUTING.md
- GOVERNANCE.md
- SECURITY.md
- SOURCE_POLICY.md
- MODEL_POLICY.md
- ROADMAP.md
- Architekturentscheidungen / ADRs
- Issue Templates
- Pull-Request-Template
- Good First Issues

## Beispiel-Issues

    good first issue:
    Neue Familienkassen-Quelle ergänzen

    good first issue:
    Synthetischen Pflegekassenbrief hinzufügen

    help wanted:
    Widerspruchsextraktion verbessern

    help wanted:
    Ukrainische Übersetzung ergänzen

    research:
    Docling-OCR auf deutschen Behördenbriefen benchmarken

# Zusammenarbeit mit öffentlichen Stellen

Interessante Gesprächspartner:

- DigitalService / NeuRIS
- Bundesportal
- Bundesagentur für Arbeit
- Deutsche Rentenversicherung
- Bundesministerium für Gesundheit
- Bundesministerium der Justiz
- Länder und Kommunen
- Civic-Tech- und Open-Data-Organisationen

Leitfrage:

> Wir bauen eine offene Zugangsschicht zu Ihren bereits öffentlichen Informationen. Welche Schnittstellen, Datenmodelle und Qualitätsanforderungen sollten wir berücksichtigen?

# Konkreter 30-Tage-Plan

## Woche 1 – Benchmark-Grundlage

- Benchmark-Schema festlegen
- Ground-Truth-Format definieren
- erste 50 synthetische Behördenbriefe
- Eval Runner implementieren
- erste Metriken berechnen

## Woche 2 – Datensatz ausbauen

- auf 200+ Dokumente erweitern
- schlechte Scans, Fotos, Drehungen und Layoutvarianten ergänzen
- Frist-, Rechtsbehelfs- und Requirements-Metriken stabilisieren
- Regressionstests in CI

## Woche 3 – Evidence Engine härten

- NeuRIS-Relevanztests
- LeiKa-/Bundesportal-Zuordnung
- weitere offizielle Leistungsquellen
- Source-Freshness-Monitoring
- klare Trennung von Gesetz, Rechtsprechung, Leistung und Dokumentevidenz

## Woche 4 – erster vollständiger Bürgerworkflow

    Jobcenter-Brief
       ↓
    OCR
       ↓
    Dokumenttyp
       ↓
    Frist
       ↓
    verlangte Unterlagen
       ↓
    Rechtsgrundlage
       ↓
    amtliche Quellen
       ↓
    verständliche Erklärung
       ↓
    Antwortentwurf / Checkliste

Derselbe Kern soll über Web und WhatsApp funktionieren.

# Kriterien für v1.0

v1.0 sollte erst erreicht werden, wenn mindestens folgende Punkte erfüllt sind:

- reproduzierbarer öffentlicher Benchmark
- sehr niedrige kritische Fristenfehlerquote
- nachvollziehbare Quellen pro wichtiger Aussage
- robuste Foto-/Scan-Verarbeitung
- mehrere vollständig getestete Behördenworkflows
- klarer Datenschutz- und Löschpfad
- reproduzierbare Self-Hosting-Dokumentation
- dokumentierte Governance
- echte externe Beiträge
- belastbare Accessibility
- kein notwendiger Vendor-Lock-in für den Kernbetrieb

## Prioritätsregel

Wenn zwischen zwei Features entschieden werden muss, gewinnt die Änderung, die mindestens eines dieser Ziele stärker verbessert:

1. **Zuverlässigkeit**
2. **Nachvollziehbarkeit**
3. **Verständlichkeit**
4. **Datenschutz**
5. **Handlungsfähigkeit der Nutzerinnen und Nutzer**

Nicht die Zahl der Features ist der Maßstab, sondern ob eine Person nach einem schwierigen Behördenbrief besser versteht, **was passiert ist, was jetzt wichtig ist und woher diese Information stammt**.
