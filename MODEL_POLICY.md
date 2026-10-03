# Modellrichtlinie

Sprachmodelle dürfen Evidenz **erklären, übersetzen und ordnen**. Sie dürfen nicht zur Quelle der rechtlichen Wahrheit werden.

## Grundregeln

- Explizite Fristen, Gesetzeszitate, Anforderungen und Rechtsbehelfe werden deterministisch extrahiert oder an amtlichen Quellen geprüft.
- Der Provider bleibt austauschbar. Der Core muss mit `LLM_PROVIDER=disabled` funktionieren.
- Die bevorzugte Produktionsoption ist ein vertraglich und technisch in Deutschland betriebener Inferenz-Endpunkt.
- Ein Konfigurationswert wie `LLM_REGION=DE` beweist keine Datenresidenz. Hosting, AVV, Unterauftragsverarbeiter, Logging, Retention und Trainingsnutzung müssen separat geprüft werden.
- Der Erklärungsschicht wird standardmäßig nicht der vollständige Originalbrief geschickt, sondern ein minimierter Evidence Context.
- Dokumente und Quellen sind Daten, keine Modellanweisungen. Prompt-Injection innerhalb eines Briefs oder Quellen-Snippets muss ignoriert werden.
- Jede generierte Aussage muss mindestens eine bekannte Evidence-ID referenzieren.
- Generierte Datums- und Paragraphenangaben müssen in der referenzierten Evidenz vorkommen; sonst wird die Aussage verworfen.
- Fällt das Modell aus oder verletzt es das Antwortschema, bleibt der deterministische Fallback aktiv.

Leitprinzip:

> **Das Modell formuliert. Die Evidenz entscheidet, was behauptet werden darf.**
