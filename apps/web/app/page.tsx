"use client";

import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_CIVIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [doc, setDoc] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(e: FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await fetch(API + "/v1/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q, language: "de", document_id: doc?.document_id }),
      });
      if (!r.ok) throw new Error(await r.text());
      setAnswer(await r.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const f = new FormData();
      f.append("file", file);
      const r = await fetch(API + "/v1/documents", { method: "POST", body: f });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setDoc(d);
      const a = await fetch(API + "/v1/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: "Was bedeutet das und was muss ich tun?",
          document_id: d.document_id,
          language: "de",
        }),
      });
      if (!a.ok) throw new Error(await a.text());
      setAnswer(await a.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <div
          className="project-logo-motion"
          role="img"
          aria-label="Drei Kreise in Schwarz, Rot und Gold, die zeitversetzt auseinander und wieder zusammen atmen, während sich der ganze Cluster langsam dreht."
        >
          <div className="project-logo-cluster">
            <span className="project-logo-circle project-logo-top" />
            <span className="project-logo-circle project-logo-left" />
            <span className="project-logo-circle project-logo-right" />
          </div>
        </div>
        <h1>Deutschland Assistent</h1>
        <p>Dokumente, Gesetze und Verwaltung verständlich machen.</p>
      </section>

      <section className="card">
        <label className="upload">
          <strong>Dokument oder Foto hochladen</strong>
          <span>PDF, Foto oder Text · Scans werden lokal mit Docling/OCR gelesen</span>
          <input
            type="file"
            accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.webp,.tif,.tiff,image/*"
            onChange={(e) => upload(e.target.files?.[0])}
          />
        </label>
        <div className="or">oder</div>
        <form onSubmit={ask}>
          <textarea value={q} onChange={(e) => setQ(e.target.value)} placeholder="z. B. Was bedeutet § 60 SGB I?" />
          <button disabled={busy}>{busy ? "Wird geprüft …" : "Frage stellen"}</button>
        </form>
      </section>

      {error && <section className="card error">{error}</section>}
      {doc && (
        <section className="card compact">
          <strong>{doc.filename}</strong> · {doc.document_type} · {doc.parsing_engine}
        </section>
      )}

      {answer && (
        <section className="card result">
          <div className="eyebrow">Das Wichtigste</div>
          <h2>{answer.what_is_this || "Antwort"}</h2>
          <p>{answer.what_does_it_mean}</p>

          {answer.deadline && (
            <div className="deadline">
              <span>Frist</span>
              <strong>{new Date(answer.deadline.date + "T12:00:00").toLocaleDateString("de-DE")}</strong>
              {answer.deadline.confidence === "low" && (
                <small className="estimate">Geschätzt, nicht verbindlich. Maßgeblich ist, wann Sie das Schreiben erhalten haben.</small>
              )}
            </div>
          )}

          {answer.relative_deadlines?.length > 0 && (
            <details className="basis">
              <summary>Wie wurde die Frist eingeordnet?</summary>
              <ul>
                {answer.relative_deadlines
                  .flatMap((r: any) => [r.raw, ...(r.basis || [])])
                  .map((x: string, i: number) => <li key={i}>{x}</li>)}
              </ul>
            </details>
          )}

          {answer.requirements?.length > 0 && (
            <>
              <h3>Was die Behörde von Ihnen verlangt</h3>
              <div className="requirements">
                {answer.requirements.map((r: any, i: number) => (
                  <div className="requirement" key={i}>
                    <strong>{r.text}</strong>
                    <span>{r.kind === "document" ? "Unterlage" : r.kind === "payment" ? "Zahlung" : r.kind === "information" ? "Angabe" : "Aufgabe"}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {answer.appeal_instruction && (
            <div className="appeal">
              <div className="eyebrow">Rechtsbehelf erkannt</div>
              <strong>{String(answer.appeal_instruction.remedy).toUpperCase()}</strong>
              {answer.appeal_instruction.deadline_expression && <p>{answer.appeal_instruction.deadline_expression}</p>}
              {answer.appeal_instruction.recipient && <p>Zuständig laut Schreiben: {answer.appeal_instruction.recipient}</p>}
              {answer.appeal_instruction.methods?.length > 0 && <p>Genannte Wege: {answer.appeal_instruction.methods.join(", ")}</p>}
            </div>
          )}

          <h3>Nächste Schritte</h3>
          <ol>{answer.what_should_i_do?.map((x: string, i: number) => <li key={i}>{x}</li>)}</ol>

          {answer.sources?.length > 0 && (
            <>
              <h3>Offizielle Quellen</h3>
              <div className="sources">
                {answer.sources.map((s: any, i: number) => (
                  <a key={i} href={s.url} target="_blank" rel="noreferrer">
                    <span>{s.kind === "official_case_law" ? "Rechtsprechung · " : ""}{s.title}</span>
                    {s.locator && <small>{s.locator}</small>}
                  </a>
                ))}
              </div>
            </>
          )}
          <p className="fine">{answer.disclaimer}</p>
        </section>
      )}

      <footer>Open Source · Quellenorientiert · Werbefrei</footer>
    </main>
  );
}
