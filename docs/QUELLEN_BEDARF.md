# Quellenbedarf – fehlende Datenbanken, Register und Behördenseiten

Stand: November 2026. Ergänzt [DATA_SOURCES.md](DATA_SOURCES.md) (was bereits angebunden ist) um das, was dem
Assistenten noch fehlt. Maßstab ist die [SOURCE_POLICY.md](../SOURCE_POLICY.md): amtliche Quellen zuerst; nicht amtliche
Quellen sind ausdrücklich markiert und dürfen höchstens als Hilfsdaten dienen, nie als Evidenz.

**Prüfstatus**
- ✅ Über Websuche im November 2026 bestätigt (Existenz und Zweck; Endpunkte vor der Anbindung nochmals prüfen).
- ☑️ Bekannte amtliche Seite, in dieser Recherche nicht gesondert verifiziert.
- ⚠️ Nicht amtlich: nur als Hilfsdaten, nie als Evidenz.

Hinweis: Aus der Entwicklungs-Sandbox waren alle hier genannten Hosts per Netzwerk-Policy gesperrt. Live-Abrufe der
Endpunkte stehen deshalb noch aus und gehören in den jeweiligen Connector-PR (inklusive `httpx.MockTransport`-Tests und einem
Eintrag im täglichen Smoke-Test).

## Bestand (zum Vergleich)

| Bereich | Heute angebunden |
|---|---|
| Bundesrecht | Gesetze im Internet (Direktlinks für **21** Gesetzeskürzel in `LAW_SLUGS`), NeuRIS-Testphase (Gesetzgebung und Rechtsprechung) |
| Leistungen | **9** kuratierte Einträge in `services.de.json`, LeiKa-ID → Bundesportal-Link |
| Termine | **5** Anliegen in `appointments.de.json`, Bundesportal-Suche mit PLZ |
| Zuständigkeit/Adressen | keine |
| Feiertage | ✅ bundesweit und je Land (Fristverschiebung nach § 193 BGB u. a.) |
| Landes- und EU-Recht | keine |
| Formulare | nur vom Nutzer hochgeladene PDFs |

---

## P0 – Kernfunktion „Behördenbrief verstehen“ ist ohne diese Quellen fehlerhaft oder lückenhaft

### 1. Gesetzliche Feiertage je Bundesland (Fristberechnung)
> ✅ **Umgesetzt** in `deutschland_assistent/feiertage.py`: eigene Berechnung nach den Landesfeiertagsgesetzen, gegengeprüft mit dem Paket `holidays` (16 Länder, 2018–2035, keine Abweichung). Das Bundesland ist optional (`bundesland` bei `/v1/documents` und `/v1/ask`, Auswahl in der Weboberfläche). Noch offen: das Bundesland automatisch aus der Behördenadresse ableiten (braucht Nr. 2).

- **Problem:** `extraction.next_weekday` verschiebt ein Fristende nur über Samstag und Sonntag. Nach § 193 BGB,
  § 31 Abs. 3 VwVfG, § 26 Abs. 3 SGB X, § 108 Abs. 3 AO und § 222 Abs. 2 ZPO verschiebt sich das Ende auch über
  **gesetzliche Feiertage am Ort**. Heute nennen wir dann ein zu frühes Fristende. Das ist auf der sicheren Seite, aber falsch.
- **Quelle:** die Feiertagsgesetze der 16 Länder (amtlich, über die Landesrechtsportale, siehe Nr. 6) sowie der
  bundesweite Tag der Deutschen Einheit (Einigungsvertrag Art. 2 Abs. 2) ☑️.
- **Umsetzung:** offline berechnen, z. B. mit dem PyPI-Paket `holidays` (Subdivisions `BW` … `TH`) ⚠️, abgesichert durch
  Tests gegen die Landesgesetze. Das Bundesland kommt aus der PLZ (Nr. 2) oder aus der Behördenadresse im Brief.
  Regionale Feiertage (Augsburger Friedensfest, Fronleichnam nur in Teilen Sachsens und Thüringens, Mariä Himmelfahrt in
  Teilen Bayerns) brauchen die Gemeinde. Ist sie unbekannt, gilt die konservative (frühere) Frist mit Hinweis.

### 2. PLZ → Gemeinde, AGS/ARS, Bundesland
Grundlage für jede Zuständigkeitsfrage (Nr. 3, 9), für Feiertage (Nr. 1) und für das Landesrecht (Nr. 6).
- **Destatis Gemeindeverzeichnis (GV-ISys)** ✅: amtlich, enthält ARS (12-stellig), AGS (8-stellig), Name, PLZ und
  Verwaltungsanschrift. Das **Anschriftenverzeichnis** im Statistikportal gibt es als kostenlosen Excel-Download, dazu
  GV100AD als ZIP-Datei.
  → <https://www.statistikportal.de/de/gemeindeverzeichnis>,
  <https://www.destatis.de/EN/Themes/Countries-Regions/Regional-Statistics/OnlineListMunicipalities/list-municipalities-information-system.html>
- **OpenPLZ API** ✅ ⚠️: offene REST-API ohne Schlüssel für PLZ, Orte, Straßen und Verwaltungsgliederung (DE/AT/CH/LI),
  Open Source (AGPL). Nicht amtlich, aber praktisch für die Straßen-Ebene, wenn eine PLZ mehrere Gemeinden abdeckt.
  → <https://openplzapi.org/de/germany/>, Code: <https://github.com/openpotato/openplzapi>
- **Umsetzung:** die amtliche Tabelle als versioniertes Datenpaket (`data/gemeinden.de.json`, mit Stichtag) einbinden,
  keine Laufzeitabhängigkeit.

### 3. PVOG – Portalverbund Online-Gateway (Leistungen **und** zuständige Stelle je Ort)
- **Was:** der bundesweite Zusammenschluss der Verwaltungsportale (FITKO). Der **Suchdienst** liefert Leistungsbeschreibungen,
  zuständige Organisationseinheiten mit Anschrift, Öffnungszeiten und Kontakt sowie Onlinedienste, jeweils je ARS.
  Der Beta-Endpunkt `/v6beta3/servicedescriptions/{ars}/detail` liefert eine Leistung mit allen zuständigen Stellen
  für einen ARS ✅. Seit 02.02.2026 liegen die APIs unter **pvog.fitko.net** (vorher pvog.fitko.de) ✅.
- **Zugang:** API-Schlüssel über ein Antragsformular im Produktportal ✅. Nutzungsbedingungen für ein Open-Source-Bürgerprojekt
  müssen beim Antrag geklärt werden.
  → <https://produktportal.pvog.fitko.de/>
- **Nutzen:** ersetzt die heutige Bundesportal-Linksuche durch „Für Ihre PLZ zuständig: Bürgeramt X, Adresse, Online-Antrag Y“.
  Das ist die mit Abstand wertvollste fehlende Quelle.

### 4. FIM-Leistungskatalog (ehemals LeiKa) und FIM-Stammtexte
- **Was:** der vollständige Katalog der Verwaltungsleistungen von Bund, Ländern und Kommunen mit bürgerverständlichen
  Stammtexten, Rechtsgrundlagen, Fristen und erforderlichen Unterlagen im Standard **XZuFi** ✅. Dazu die
  FIM-Stammdatenschemata (**XDatenfelder**: amtliche Feldnamen von Antragsformularen) ✅.
- **Wo:** FIM-Portal (manueller Zugriff) und das FIM-Sammelrepository mit maschinenlesbaren Schnittstellen ✅;
  Standards im XRepository.
  → <https://fimportal.de/>, <https://www.xrepository.de/>
- **Nutzen:** das Leistungsregister wächst von 9 auf tausende Einträge, jeweils mit LeiKa-ID. Die XDatenfelder
  verbessern die Feldzuordnung des Formular-Agenten.

### 5. Gesetze im Internet – vollständiges XML-Inhaltsverzeichnis
- **Was:** `https://www.gesetze-im-internet.de/gii-toc.xml`, ein tagesaktuelles Verzeichnis aller über 6.000
  Bundesgesetze und -verordnungen, je Gesetz mit `xml.zip` ✅. Es enthält nur konsolidierte Fassungen, keine Änderungsgesetze.
  → <https://www.gesetze-im-internet.de/hinweise.html>
- **Problem heute:** nur 21 Kürzel haben einen Direktlink. Für alle anderen (z. B. WoGG, BEEG, UVG, BAföG, BKGG, RBEG,
  AufenthG, StVG, OWiG, RBStV) erscheint nur die Startseite.
- **Umsetzung:** Build-Schritt erzeugt eine Kürzel→Slug-Tabelle aus dem Inhaltsverzeichnis. Die Normtexte können
  optional lokal indiziert werden; dann gibt es Snippets ohne Live-Abfrage.

---

## P1 – deutlich bessere Antworten

### 6. Landesrecht (16 Portale)
NeuRIS deckt bisher nur Bundesrecht ab. Kommunalabgaben, Schulrecht, Polizeirecht, Feiertage, Landesbauordnung und
landesrechtliche Bescheide (z. B. Kita-Gebühren) brauchen Landesrecht ☑️:

| Land | Portal |
|---|---|
| BW | <https://www.landesrecht-bw.de/> |
| BY | <https://www.gesetze-bayern.de/> |
| BE | <https://gesetze.berlin.de/> |
| BB | <https://bravors.brandenburg.de/> |
| HB | <https://www.transparenz.bremen.de/> |
| HH | <https://www.landesrecht-hamburg.de/> |
| HE | <https://www.rv.hessenrecht.hessen.de/> |
| MV | <https://www.landesrecht-mv.de/> |
| NI | <https://voris.wolterskluwer-online.de/> |
| NW | <https://recht.nrw.de/> |
| RP | <https://landesrecht.rlp.de/> |
| SL | <https://recht.saarland.de/> |
| SN | <https://www.revosax.sachsen.de/> ✅ |
| ST | <https://www.landesrecht.sachsen-anhalt.de/> |
| SH | <https://www.gesetze-rechtsprechung.sh.juris.de/> |
| TH | <https://landesrecht.thueringen.de/> |

Vorgehen: zunächst nur Deep-Links pro Land und Kürzel (wie heute bei Gesetze im Internet). Volltext erst, wenn ein Land
eine offene Schnittstelle anbietet oder NeuRIS Landesrecht aufnimmt.

### 7. Verkündung und Inkrafttreten: Bundesgesetzblatt online
- <https://www.recht.bund.de/>: seit 2023 die amtliche, kostenlose elektronische Ausgabe mit **ELI**-URLs
  (z. B. `/eli/bund/BGBl_1/2023/1`) sowie RSS und E-Mail-Benachrichtigungen ✅. Das Archiv 1949–2022 liegt auf bgbl.de.
- **Nutzen:** Änderungsgesetze und Inkrafttreten nachweisen („gilt das schon?“), z. B. bei Reformen des Bürgergelds
  bzw. der Grundsicherung. Eine dokumentierte API haben wir nicht gefunden; zunächst nur RSS und ELI-Links.

### 8. EU-Recht: EUR-Lex / Cellar
- SOAP-Webservice (kostenlos nach Registrierung), **Cellar SPARQL** (`http://publications.europa.eu/webapi/rdf/sparql`)
  und Cellar-REST für Dokumente ✅.
  → <https://eur-lex.europa.eu/content/help/data-reuse/webservice.html>
- **Nutzen:** DSGVO-Auskunftsersuchen, Freizügigkeit, Koordinierung der sozialen Sicherheit (VO 883/2004),
  Verbraucherrechte. CELEX- und ELI-Identifier passen zum vorhandenen Evidenzmodell.

### 9. Behörden- und Gerichtsfinder (Zuständigkeit für Antworten, Widerspruch und Klage)
| Zweck | Quelle | Status |
|---|---|---|
| Zuständiges **Finanzamt** nach AGS, PLZ oder Straße | BZSt **GemFA**, maschinenlesbar als XML auf der Finanzamtsuche | ✅ |
| Zuständiges **Amts-, Land- oder Oberlandesgericht**, Adressen | Justizportal: Orts- und Gerichtsverzeichnis <https://justiz.de/orts_gerichtsverzeichnis/index.php> | ✅ (Abdeckung von Sozial- und Verwaltungsgerichten unklar) |
| **Sozial- und Verwaltungsgerichte** (für die Klage nach dem Widerspruchsbescheid) | Gerichtsverzeichnisse der Länder, z. B. Justiz NRW „Adresskarten A bis Z“ | ✅ teilweise |
| **Jobcenter / Agentur für Arbeit** | Dienststellensuche auf arbeitsagentur.de | ☑️ |
| **Familienkasse** | Familienkassen-Suche auf arbeitsagentur.de | ☑️ |
| **Deutsche Rentenversicherung**: Beratungsstellen, zuständiger Träger | deutsche-rentenversicherung.de | ☑️ |
| **Krankenkassen** (Liste, Kontakt) | GKV-Spitzenverband, Krankenkassenliste | ☑️ |
| **Ausländerbehörden**, Integrationskurse | BAMF-NAvI und Behördensuche, bamf.de | ☑️ |
| Alle übrigen kommunalen Stellen | PVOG (Nr. 3) | ✅ |

Nutzen: Der Brief-Agent kann in Widerspruch, Fristverlängerung und Nachreichung die richtige Empfängeranschrift
vorschlagen. Die Adresse aus dem Brief bleibt vorrangig.

### 10. Verwaltungsvorschriften und fachliche Weisungen (wie Behörden das Recht tatsächlich anwenden)
| Bereich | Quelle | Status |
|---|---|---|
| Bund allgemein | verwaltungsvorschriften-im-internet.de (soll laut BT-Drs. 20/3854 im neuen Rechtsportal aufgehen) | ✅ |
| SGB II / SGB III | **Fachliche Weisungen der BA**, z. B. FW § 5, § 16, § 19 SGB II mit Stand-Datum, als PDF auf arbeitsagentur.de | ✅ |
| Kindergeld | Durchführungsanweisungen Kindergeld (DA-KG), BZSt/BA | ☑️ |
| Rente | **rvRecht**: Rechtliche Arbeitsanweisungen der DRV | ☑️ |
| Steuern | BMF-Schreiben, Anwendungserlass zur AO (AEAO), bundesfinanzministerium.de | ☑️ |

Diese Quellen sind als eigene Evidenzart `administrative_guidance` zu kennzeichnen: amtlich, aber kein Gesetz.

### 11. Amtliche Kennzahlen mit Gültigkeitszeitraum
Viele Briefe prüfen sich an Beträgen. Vorgeschlagen ist ein versioniertes Register `data/kennzahlen.de.json`
(Wert, gültig von/bis, Fundstelle mit ELI/BGBl) ☑️:
- Regelbedarfsstufen (Regelbedarfsstufen-Fortschreibungsverordnung, jährlich)
- Pfändungsfreigrenzen (Pfändungsfreigrenzenbekanntmachung, jährlich zum 1. Juli, BGBl)
- Mindestlohn (Mindestlohnanpassungsverordnung)
- Kindergeld, Kinderzuschlag (Höchstbetrag), Unterhaltsvorschuss, BAföG-Bedarfssätze
- Beitragsbemessungsgrenzen und Sozialversicherungsrechengrößen-Verordnung
- Rundfunkbeitrag (Rundfunkbeitragsstaatsvertrag)
- Düsseldorfer Tabelle (OLG Düsseldorf; Leitlinie, kein Gesetz, entsprechend kennzeichnen)

### 12. Amtliche Formulare (für den Formular-Agenten)
| Quelle | Inhalt | Status |
|---|---|---|
| Formular-Management-System des Bundes, <https://www.formulare-bfinv.de/> | Bundesformulare (Zoll, Bundesbehörden), oft als AcroForm | ☑️ |
| Justizportal: Formulare, <https://www.justiz.de/formulare/> | Beratungshilfe, Prozesskostenhilfe, Pfändungsschutz | ☑️ |
| Arbeitsagentur / Familienkasse | Kindergeld- und KiZ-Anträge, Veränderungsmitteilungen | ☑️ |
| DRV-Formularpaket | Rentenanträge, Kontenklärung | ☑️ |
| XDatenfelder (FIM, Nr. 4) | amtliche Feldsemantik für die Zuordnung | ✅ |

---

## P2 – Ausbau des Leistungs- und Terminregisters

### 13. Fehlende Leistungen in `services.de.json`
Häufige Briefe ohne Registereintrag. Bevorzugt aus dem FIM-Katalog (Nr. 4) übernehmen, sonst die amtliche Fachseite ☑️:
Wohngeld (BMWSB) · Unterhaltsvorschuss · Bildung und Teilhabe · Sozialhilfe und Grundsicherung im Alter (SGB XII) ·
Asylbewerberleistungen · Krankengeld · Mutterschaftsgeld (Bundesamt für Soziale Sicherung) · Schwerbehinderung und
Versorgungsamt · Pflegegrad-Begutachtung (Medizinischer Dienst) · Befreiung bzw. Ermäßigung vom Rundfunkbeitrag
(rundfunkbeitrag.de) · Kfz-Steuer (Zoll) · Steuer-ID (BZSt) · Einkommensteuer, ELSTER (elster.de) ·
Punkte und Fahreignungsregister (KBA) · Führungszeugnis online (Bundesamt für Justiz) · Aufenthalt und Einbürgerung (BAMF) ·
Anerkennung ausländischer Berufsabschlüsse (anerkennung-in-deutschland.de) · Mahnbescheid (online-mahnantrag.de) ·
Berufsausbildungsbeihilfe · Elterngeld Plus und Partnerschaftsbonus · Behördennummer 115 (115.de).

### 14. Weitere Termin-Anliegen in `appointments.de.json` und Terminsysteme
- Anliegen: Abmeldung bzw. Umzug ins Ausland, Kfz ab- und ummelden, Führerschein (Umschreibung, Ersatz),
  Eheschließung und Geburtsurkunde (Standesamt), Gewerbeanmeldung, Wohnberechtigungsschein, Elektronischer Aufenthaltstitel,
  Beglaubigungen.
- Buchungssysteme gibt es nur kommunal. Beispiel Berlin: Das Open-Source-Terminsystem „eappointment / ZMS“ hat
  dokumentierte Exportformate der Dienstleistungsdatenbank (Leistungen mit Termin-Links, Standorte, Öffnungszeiten) ✅
  (Packagist `eappointment/zmsdldb`). Die genaue Endpunkt-URL und die Lizenz sind noch offen. Jede Anbindung ist ein
  eigener, bestätigungspflichtiger Connector (siehe Skill `agentenaktion`).

### 15. Register zur Echtheitsprüfung von Schreiben (Betrugsschutz)
| Frage im Brief | Quelle | Status |
|---|---|---|
| Ist das Inkassounternehmen registriert? | **Rechtsdienstleistungsregister**, <https://www.rechtsdienstleistungsregister.de/> | ☑️ |
| Gibt es die Firma bzw. den Gläubiger? | Handelsregister (seit 2022 kostenfrei), <https://www.handelsregister.de/>; Unternehmensregister | ☑️ |
| Läuft ein Insolvenzverfahren? | <https://www.insolvenzbekanntmachungen.de/> | ☑️ |
| Ist die IBAN plausibel bzw. gehört sie zur Behörde? | Bankleitzahlendatei der Bundesbank | ☑️ |

Wichtig für Fake-Bescheide und unseriöse Inkassoschreiben, eine häufige Bürgerfrage.

### 16. Mehrsprachige, kommunale Integrationsinformationen
- **Integreat** ✅ ⚠️ (kommunal gepflegte Inhalte, Open Source unter MIT, mehrsprachig, API im Django-CMS
  `digitalfabrik/integreat-cms`). Inhalte stammen von Kommunen, die Plattform selbst ist nicht amtlich.
  → <https://github.com/digitalfabrik/integreat-cms>
- BAMF-Angebote, Make it in Germany (Bundesregierung) ☑️.

### 17. Rechtsprechung der Länder
NeuRIS enthält Bundesgerichte. Für Sozial-, Verwaltungs- und Finanzgerichte der Länder gibt es die Landesportale
(z. B. NRWE für NRW, Bürgerservice Bayern, juris-Landesportale) ☑️. Niedrige Priorität: Landesentscheidungen sind für
Bürgerantworten selten tragend.

### 18. Entdecken weiterer Schnittstellen
- **bund.dev / github.com/bundesAPI** ✅: von der Bundesstelle für Open Data betriebene OpenAPI-Dokumentation von
  Bundes-Schnittstellen. Relevant sind z. B. die BA-Jobsuche (für SGB-II/III-Kontexte), DIP Bundestag
  (Gesetzgebungsverfahren) und NINA-Warnungen.
- **GovData.de** (CKAN-API) ☑️: Metadatenkatalog offener Verwaltungsdaten.

---

## Empfohlene Reihenfolge

1. **Feiertage (Nr. 1) und PLZ→AGS (Nr. 2):** offline, ohne Fremdabhängigkeit, und sie beheben einen echten Fristfehler.
2. **gii-toc.xml (Nr. 5):** Direktlinks für alle Bundesgesetze.
3. **PVOG-API-Schlüssel beantragen (Nr. 3)** und parallel den FIM-Katalog importieren (Nr. 4).
4. Kennzahlen-Register (Nr. 11), Behörden- und Gerichtsfinder (Nr. 9), dann Landesrecht-Deep-Links (Nr. 6).
5. Fachliche Weisungen (Nr. 10), EUR-Lex (Nr. 8), BGBl (Nr. 7), Echtheitsprüfung (Nr. 15), Registerausbau (Nr. 13, 14).

Jede neue Quelle wird nach dem Skill `.claude/skills/amtliche-quelle-hinzufuegen` angebunden: Herausgeber, Abrufdatum,
Version, Lizenz, Tests mit `MockTransport` und ein Eintrag in `/v1/sources` sowie in `DATA_SOURCES.md`.

## Rechercheverweise
- PVOG: Produktportal und UserGroup-Protokolle vom 30.10.2025 und 29.01.2026, <https://produktportal.pvog.fitko.de/>
- FIM / XZuFi / XDatenfelder: <https://fimportal.de/>, <https://www.xrepository.de/>
- Gesetze im Internet, Hinweise zum XML-Inhaltsverzeichnis: <https://www.gesetze-im-internet.de/hinweise.html>
- NeuRIS / Rechtsportal: <https://digitalservice.bund.de/en/projects/new-legal-information-system>, BT-Drs. 20/3854
- Gemeindeverzeichnis: <https://www.statistikportal.de/de/gemeindeverzeichnis>
- OpenPLZ API: <https://github.com/openpotato/openplzapi>
- EUR-Lex-Webservice: <https://eur-lex.europa.eu/content/help/data-reuse/webservice.html>
- Justizportal, Orts- und Gerichtsverzeichnis: <https://justiz.de/orts_gerichtsverzeichnis/index.php>
- BZSt GemFA (beschrieben in einem Dokument des LGLN Niedersachsen): <https://lgln.niedersachsen.de/download/157336>
- Fachliche Weisungen SGB II: z. B. <https://www.arbeitsagentur.de/datei/fachliche-weisungen-p-5-sgb-ii_ba056913.pdf>
- bund.dev: <https://github.com/bundesAPI>
- Integreat: <https://github.com/digitalfabrik/integreat-cms>
- Berlin eappointment/ZMS: <https://packagist.org/packages/eappointment/zmsdldb>
