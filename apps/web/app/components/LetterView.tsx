"use client";

import { FormEvent, useEffect, useState } from "react";
import { describeError, LetterDraft, LetterKind, postJson } from "../lib/api";

type Props = {
  kind: LetterKind;
  documentId?: string;
  onBack: () => void;
};

const KINDS: { kind: LetterKind; label: string; hint: string }[] = [
  { kind: "widerspruch", label: "Widerspruch", hint: "Sie sind mit einem Bescheid nicht einverstanden." },
  { kind: "fristverlaengerung", label: "Mehr Zeit", hint: "Sie brauchen länger für eine verlangte Antwort." },
  { kind: "nachreichung", label: "Nachreichen", hint: "Sie schicken verlangte Unterlagen." },
];

/** Renders text and highlights [placeholders] the person still has to fill in. */
function Highlighted({ text }: { text: string }) {
  const parts = text.split(/(\[[^\]]+\])/g);
  return (
    <>
      {parts.map((p, i) => (p.startsWith("[") && p.endsWith("]") ? <mark key={i} className="gap">{p}</mark> : <span key={i}>{p}</span>))}
    </>
  );
}

export default function LetterView({ kind: initialKind, documentId, onBack }: Props) {
  const [kind, setKind] = useState<LetterKind>(initialKind);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [place, setPlace] = useState("");
  const [reference, setReference] = useState("");
  const [recipient, setRecipient] = useState("");
  const [reason, setReason] = useState("");
  const [until, setUntil] = useState("");
  const [items, setItems] = useState("");
  const [draft, setDraft] = useState<LetterDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function build(e?: FormEvent) {
    e?.preventDefault();
    setError(null);
    try {
      const d = await postJson<LetterDraft>("/v1/letters/draft", {
        kind,
        document_id: documentId,
        sender_name: name || null,
        sender_address: address || null,
        place: place || null,
        reference: reference || null,
        recipient: recipient || null,
        reason: reason || null,
        requested_until: until || null,
        items: items.split("\n").map((x) => x.trim()).filter(Boolean),
      });
      setDraft(d);
    } catch (err) {
      setError(describeError(err));
    }
  }

  useEffect(() => {
    build();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  async function copy() {
    if (!draft) return;
    await navigator.clipboard.writeText(draft.full_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <main className="tool letter-view">
      <div className="tool-bar">
        <button type="button" className="link-button" onClick={onBack}>‹ Zurück</button>
        {documentId && <span className="pill">Mit Angaben aus Ihrem Brief</span>}
      </div>
      <header className="tool-head">
        <h1>Antwortschreiben.</h1>
        <p>Fertiger Entwurf zum Prüfen, Unterschreiben und Absenden. Abgeschickt wird nichts automatisch.</p>
      </header>

      <div className="segmented" role="tablist" aria-label="Art des Schreibens">
        {KINDS.map((k) => (
          <button key={k.kind} type="button" role="tab" aria-selected={kind === k.kind} className={kind === k.kind ? "seg seg-on" : "seg"} onClick={() => setKind(k.kind)}>
            {k.label}
          </button>
        ))}
      </div>
      <p className="seg-hint">{KINDS.find((k) => k.kind === kind)?.hint}</p>

      <div className="tool-grid">
        <form className="card fields" onSubmit={build}>
          <label>Ihr Name<input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
          <label>Ihre Anschrift<textarea rows={2} value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="street-address" /></label>
          <label>Ort für das Datum<input value={place} onChange={(e) => setPlace(e.target.value)} autoComplete="address-level2" /></label>
          <label>Aktenzeichen <span className="optional">falls nicht erkannt</span><input value={reference} onChange={(e) => setReference(e.target.value)} /></label>
          <label>Empfänger <span className="optional">falls nicht erkannt</span><textarea rows={2} value={recipient} onChange={(e) => setRecipient(e.target.value)} /></label>
          {kind === "fristverlaengerung" && (
            <label>Neue Frist bis<input type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></label>
          )}
          {kind === "nachreichung" && (
            <label>Beigefügte Unterlagen <span className="optional">eine pro Zeile</span><textarea rows={3} value={items} onChange={(e) => setItems(e.target.value)} /></label>
          )}
          <label>
            {kind === "widerspruch" ? "Begründung" : kind === "fristverlaengerung" ? "Grund" : "Ergänzung"}{" "}
            <span className="optional">{kind === "widerspruch" ? "kann auch später folgen" : "optional"}</span>
            <textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          <button type="submit" className="button">Entwurf aktualisieren</button>
          <p className="fine left">Ihre Angaben werden nur für diesen Entwurf verwendet und nicht gespeichert.</p>
        </form>

        <div>
          {error && <p className="error" role="alert">{error}</p>}
          {draft && (
            <>
              {draft.warnings.map((w, i) => <p key={i} className="notice notice-warn">{w}</p>)}
              <article className="letter-paper" aria-label="Briefentwurf">
                <div className="lp-sender"><Highlighted text={draft.sender_block} /></div>
                <div className="lp-recipient"><Highlighted text={draft.recipient_block} /></div>
                <div className="lp-date"><Highlighted text={draft.place_date} /></div>
                <div className="lp-subject"><Highlighted text={draft.subject} /></div>
                <div className="lp-body"><Highlighted text={draft.body} /></div>
              </article>
              {draft.missing.length > 0 && (
                <p className="notice">Noch offen: {draft.missing.join(", ")}.</p>
              )}
              <div className="tool-actions">
                <button type="button" className="button" onClick={() => window.print()}>Drucken oder als PDF sichern</button>
                <button type="button" className="link-button" onClick={copy}>{copied ? "Kopiert" : "Text kopieren"}</button>
              </div>
              <section className="card">
                <h2>So geht es weiter</h2>
                <ol className="steps">
                  {draft.notes.map((n, i) => <li key={i}><span className="step-num" aria-hidden="true">{i + 1}</span><span>{n}</span></li>)}
                </ol>
                {draft.legal.length > 0 && (
                  <div className="chips">
                    {draft.legal.map((l) => <a key={l.url} className="chip" href={l.url} target="_blank" rel="noreferrer">{l.label}</a>)}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
