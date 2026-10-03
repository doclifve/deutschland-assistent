<p align="center">
  <img src="assets/logo-animated.svg" alt="Deutschland Assistent Logo: drei Kreise in Schwarz, Rot und Gold, die atmen und sich langsam drehen" width="220" />
</p>

# Deutschland Assistent 🇩🇪

**Open-Source-Bürgerassistent für Deutschland: Behördenpost, Gesetze, Leistungen und nächste Schritte verständlich machen – mit nachvollziehbaren Quellen.**

Deutschland Assistent ist ein quelloffener, evidenzorientierter Bürgerassistent. Ziel ist, deutsche Verwaltung, Gesetze und persönliche Behördenpost verständlicher zu machen, ohne dass Nutzerinnen und Nutzer juristische Fachbegriffe, Behördenstrukturen oder besondere KI-Prompts kennen müssen.

> **Grundprinzip:** Das Modell ist nicht die Quelle der Wahrheit. Maßgeblich sind das Originaldokument und amtliche Quellen.

<p align="center">
  <img src="docs/screenshots/iphone.png" alt="Deutschland Assistent auf dem iPhone" width="860" />
</p>

<details>
<summary>iPad-Ansicht</summary>
<p align="center">
  <img src="docs/screenshots/ipad.png" alt="Deutschland Assistent auf dem iPad" width="760" />
</p>
</details>

## Was v0.2.2 bereits kann

- PDFs, Textdateien sowie **Fotos und Scans** verarbeiten.
- Text, Datumsangaben, Fristen und häufige Rechtsverweise erkennen.
- Dokumente auch ohne LLM oder externen Modell-API-Schlüssel analysieren.
- **Docling lokal** für OCR und Layout-Erkennung bei Fotos, Scans und textarmen PDFs einsetzen; entfernte Docling-Dienste sind deaktiviert.
- Fristen, Rechtsverweise, LeiKa-IDs, Behördenhinweise sowie **angeforderte Unterlagen, Handlungen, Zahlungen** und **Rechtsbehelfsbelehrungen** strukturiert erkennen.
- Relative Fristen wie „innerhalb eines Monats nach Bekanntgabe“ erkennen und konservativ ein mögliches Fristende schätzen. Geschätzte Fristen werden ausdrücklich als unsicher gekennzeichnet.
- Hochgeladene Dokumente standardmäßig nur temporär im Speicher halten, mit Ablaufzeit, Größenbegrenzung und Lösch-Endpunkt.
- Explizite Gesetzeszitate direkt mit **Gesetze im Internet** verknüpfen.
- Bundesrecht und Rechtsprechung über die öffentliche **NeuRIS**-Schnittstelle durchsuchen; exakte Gesetzeszitate behalten einen direkten amtlichen Fallback.
- Häufige Leistungen gegen ein nachvollziehbares Register offizieller Quellen abgleichen.
- Strukturierte, gerankte Evidenz zu einer Antwort zurückgeben.
- Fragen über eine einfache Weboberfläche stellen.
- WhatsApp anbinden: Texte, Fotos und Dokumente können über die WhatsApp Cloud API in denselben Analyse-Workflow gelangen.
- OpenClaw als optionalen Kanal-/Agent-Gateway nutzen, ohne die fachliche Logik dorthin zu verlagern.

## Was eine Dokumentantwort enthalten soll

Nach dem Upload oder Foto eines Behördenbriefs kann der Assistent Informationen getrennt ausgeben:

- **Was ist das für ein Schreiben?**
- **Was bedeutet es?**
- **Welche Frist wurde erkannt?**
- **Was verlangt die Behörde?**
- **Welche Unterlagen fehlen?**
- **Gibt es einen Rechtsbehelf wie Widerspruch oder Klage?**
- **Welche Rechtsgrundlagen werden genannt?**
- **Welche amtlichen Quellen passen dazu?**
- **Was sind sinnvolle nächste Schritte?**
- **Was ist noch unsicher oder unklar?**

## Leitstern des Projekts

Der wichtigste End-to-End-Anwendungsfall ist bewusst einfach:

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

Alles, was diesen Ablauf zuverlässiger, verständlicher oder sicherer macht, hat Vorrang vor zusätzlicher Oberfläche.

## Architektur

                          Bürger:in
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
           Web            OpenClaw          WhatsApp
            │          optionaler Gateway       │
            └─────────────────┼─────────────────┘
                              ▼
                      Channel Gateway
                              │
                              ▼
                  Deutschland Assistent Core
        Intent → Dokument → Retrieval → Evidence
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
              Docling      Rechtsquellen  Leistungen
                OCR
                              │
                              ▼
                       Evidence Engine
                              │
                              ▼
                    strukturierte Antwort
                              │
                              ▼
                      verständliche Ausgabe

### Architekturregeln

- **Kanäle sind Adapter.** WhatsApp, OpenClaw oder Web enthalten keine eigene Rechtslogik.
- **Evidenz ist ein Kernobjekt.** Wichtige Aussagen sollen auf Dokumentstellen oder amtliche Quellen zurückführbar sein.
- **Folgenreiche Aktionen brauchen Bestätigung.** Anträge, Widersprüche, Kündigungen oder andere rechtlich relevante Erklärungen werden nicht autonom abgeschickt.
- **Kein Modell-Lock-in.** Der deterministische Kern funktioniert ohne LLM; Modelle können hinter einer Provider-Schnittstelle ergänzt werden.
- **Minimale Datenhaltung.** Persönliche Dokumente sollen standardmäßig nur so lange gespeichert werden, wie es für die Verarbeitung nötig ist.
- **Unsicherheit bleibt sichtbar.** Eine geschätzte Frist oder ein semantischer Suchtreffer darf nicht wie eine amtlich feststehende Tatsache aussehen.

## Projektplan

Die ausführliche Planung liegt in [docs/PROJEKTPLAN.md](docs/PROJEKTPLAN.md).

| Phase | Ziel |
|---|---|
| **v0.2.3** | Öffentlicher Behördenbrief-Benchmark und messbare Qualitätsmetriken |
| **v0.2.4** | Evidence Engine 2.0 mit breiterer amtlicher Wissensschicht und Source Monitoring |
| **v0.3** | Bürger-Workflows: von „verstehen“ zu „vorbereitet handeln“ |
| **v0.4** | Mehrsprachigkeit, Einfache Sprache und Barrierefreiheit |
| **v0.5** | Produktionshärtung, Skalierung, Observability und Datenschutz |
| **v1.0** | Belastbare offene Bürger-Infrastruktur für Deutschland |

Die kompakte Release-Roadmap steht in [docs/ROADMAP.md](docs/ROADMAP.md).

## Schnellstart

### Variante A – Docker

    cp .env.example .env
    docker compose up --build

Danach:

- Web: http://localhost:3000
- API-Dokumentation: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/health

### Variante B – ohne Docker

Benötigt Python 3.11+ und Node.js 20+.

Backend:

    cd services/civic-core
    python3.12 -m venv .venv
    source .venv/bin/activate
    pip install -e '.[dev]'
    python -m uvicorn deutschland_assistent.main:app --reload --port 8000

Weboberfläche:

    cd apps/web
    npm install
    npm run dev

Docling/OCR lokal installieren:

    pip install -e '.[docling]'

## Beispiel-API

Frage stellen:

    curl -X POST http://localhost:8000/v1/ask \
      -H 'Content-Type: application/json' \
      -d '{"message":"Was bedeutet § 60 SGB I?","language":"de"}'

Dokument hochladen:

    curl -X POST http://localhost:8000/v1/documents \
      -F 'file=@bescheid.pdf'

## Wichtige API-Endpunkte

- POST /v1/evidence/search – amtliche Wissensschicht durchsuchen.
- GET /v1/sources – Quellen, Rollen und Status anzeigen.
- GET /v1/channels – öffentliche Verbindungsdaten für Kommunikationskanäle ausgeben.
- POST /v1/documents – Dokument analysieren und strukturierte Fakten extrahieren.
- DELETE /v1/documents/{id} – hochgeladenes Dokument vor Ablauf der TTL löschen.
- POST /v1/ask – Dokumentinformationen und amtliche Evidenz zu einer Antwort verbinden.

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---|---|
| CORS_ORIGINS | http://localhost:3000 | erlaubte Origins |
| DOCUMENT_ENGINE | auto | basic, docling oder auto |
| MAX_UPLOAD_BYTES | 15728640 | maximale Uploadgröße |
| MAX_DOCUMENT_PAGES | 30 | maximale Seitenzahl pro Dokument |
| DOCLING_ARTIFACTS_PATH | /opt/docling-models | lokaler Docling-Modellcache |
| PREFETCH_DOCLING_MODELS | 0 | Docling-Modelle beim Image-Build vorladen |
| DOCUMENT_TTL_SECONDS | 3600 | Verweildauer eines Dokuments im Speicher |
| MAX_STORED_DOCUMENTS | 500 | maximale Zahl gleichzeitig gespeicherter Dokumente |
| WHATSAPP_PUBLIC_NUMBER | – | öffentliche WhatsApp-Nummer im E.164-Format |
| WHATSAPP_GREETING | Hallo | vorausgefüllte Begrüßung im Chat |
| WHATSAPP_APP_SECRET | – | Prüfung der Meta-Webhook-Signatur; in Produktion erforderlich |
| MAX_WHATSAPP_MEDIA_BYTES | 15728640 | maximale WhatsApp-Mediendateigröße |

## WhatsApp

<p align="center">
  <img src="docs/screenshots/whatsapp.png" alt="WhatsApp-Verbindung des Deutschland Assistent" width="860" />
</p>

Über WhatsApp kann eine Person einen Text, ein Foto oder ein PDF senden. Der Adapter übergibt die Nachricht an denselben Dokument- und Evidence-Workflow wie die Weboberfläche und sendet die strukturierte Antwort zurück.

    Web-App ──GET /v1/channels──▶ Civic Core
    WhatsApp ──Webhook──▶ WhatsApp-Cloud-Adapter ──▶ /v1/documents + /v1/ask
                                                 │
                                                 └──▶ WhatsApp Cloud API

### Einrichtung

1. In der Meta-Entwickleroberfläche eine App mit dem Produkt **WhatsApp** erstellen und eine Geschäftsnummer registrieren.
2. Die nötigen Werte in .env hinterlegen.
3. Stack inklusive Adapter starten:

       docker compose --profile whatsapp up --build

4. Den Adapter über HTTPS erreichbar machen und /webhook in Meta hinterlegen.
5. Eine Nachricht oder ein Dokument an die Nummer senden.

**Hinweis:** WhatsApp ist ein externer Dienst von Meta. Eine Nutzung über WhatsApp ist daher datenschutztechnisch nicht identisch mit einem lokal oder selbst gehosteten Web-Upload.

## OpenClaw

Der optionale OpenClaw-Skill liegt unter channels/openclaw/deutschland-assistent/.

    openclaw skills install ./channels/openclaw/deutschland-assistent --as deutschland-assistent
    export DEUTSCHLAND_ASSISTENT_API=http://localhost:8000

Die Integration bleibt bewusst schmal: Sie leitet Bürgerfragen und Dokumentanalysen an den Civic Core weiter. Unbeschränkter Shell-, Browser- oder Dateisystemzugriff gehört nicht in einen öffentlich erreichbaren Agenten.

## Repository-Struktur

    apps/web/                                   Bürgeroberfläche
    services/civic-core/                        FastAPI-Kern
      deutschland_assistent/extraction.py       deterministische Extraktion
      deutschland_assistent/evidence.py         amtliche Evidence Engine
      deutschland_assistent/documents.py        PDF-/OCR-Dokumentverarbeitung
      deutschland_assistent/schemas.py          Antwort- und Evidenzschema
    channels/openclaw/                          optionaler OpenClaw-Skill
    channels/whatsapp-cloud/                    WhatsApp-Cloud-Adapter
    docs/                                       Architektur, Quellen, Roadmap, Projektplan

## Amtliche Datenquellen

Die Quellenstrategie ist bewusst konservativ. Bevor eine Quelle als maßgeblich behandelt wird, sollen Herkunft, Zuständigkeit, Format und Aktualität nachvollziehbar sein.

Aktuell bzw. vorgesehen:

- **Gesetze im Internet**
- **Rechtsinformationen des Bundes / NeuRIS**
- **Bundesportal / LeiKa**
- **Bundesagentur für Arbeit / Familienkasse**
- **Deutsche Rentenversicherung**
- **Bundesministerium für Gesundheit**
- weitere amtliche Bundes-, Landes- und Kommunalquellen

Details: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)

## Sicherheit und rechtliche Grenzen

Deutschland Assistent soll **Informationszugang und Unterstützung** bieten, aber keine autonome Rechtsentscheidung treffen.

Bei rechtlich relevanten Aktionen gilt:

    Vorbereiten
       ↓
    Vorschau
       ↓
    ausdrückliche Bestätigung
       ↓
    Ausführen

Siehe außerdem:

- [Sicherheit](SECURITY.md)
- [Quellenrichtlinie](SOURCE_POLICY.md)
- [Modellrichtlinie](MODEL_POLICY.md)
- [Transparenz](TRANSPARENCY.md)
- [Threat Model](docs/THREAT_MODEL.md)

## Mitmachen

Beiträge sind ausdrücklich willkommen. Besonders hilfreich sind:

- neue amtliche Quellen und Connectoren,
- synthetische oder vollständig anonymisierte Testdokumente,
- bessere Extraktion von Fristen und Behördenanforderungen,
- Übersetzungen und Einfache Sprache,
- Accessibility,
- Sicherheitsprüfungen,
- Evaluations- und Benchmarking-Arbeit.

Bitte keine echten Bürgerdokumente, Zugangsdaten oder personenbezogenen Daten committen.

Siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Entwicklung und Tests

    make test

Neue Funktionen mit potenziell großen Folgen für Bürgerinnen und Bürger sollten nicht nur neue Features, sondern auch passende Tests und Evaluationen mitbringen.

## Status

**v0.2.2 – frühe Alpha-Version.**

Die OCR-Dokumentverarbeitung, strukturierte Extraktion von Anforderungen und Rechtsbehelfen sowie die amtliche Evidence Engine sind implementiert. Schnittstellen und Datenmodelle können sich noch ändern.

## Lizenz

Eigener Projektcode steht – sofern in einzelnen Dateien nicht anders angegeben – unter **Apache-2.0**. Externe Komponenten und Datenquellen behalten ihre jeweiligen Lizenzen und Nutzungsbedingungen.

## Logo-Animation

Das Logo ist bewusst lebendig: Die drei Kreise in Schwarz, Rot und Gold bewegen sich zeitversetzt auseinander und wieder zusammen, während sich der gesamte Cluster langsam dreht. Durch die Überlagerungen entstehen wechselnde Farbmischungen.

Die README verwendet assets/logo-animated.svg. Die Web-App nutzt eine eigene CSS-Animation. Bei aktivierter Systemeinstellung „Bewegung reduzieren“ wird die Bewegung entsprechend reduziert bzw. deaktiviert.
