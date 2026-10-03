"use client";

import { useRef, useState } from "react";
import { describeError, FormField, FormInfo, FormSuggestions, postFile, postForBlob, postJson } from "../lib/api";

type Props = {
  documentId?: string;
  onBack: () => void;
};

const PROFILE: { key: string; label: string; auto?: string }[] = [
  { key: "vorname", label: "Vorname", auto: "given-name" },
  { key: "nachname", label: "Nachname", auto: "family-name" },
  { key: "geburtsdatum", label: "Geburtsdatum", auto: "bday" },
  { key: "geburtsort", label: "Geburtsort" },
  { key: "strasse", label: "Straße", auto: "address-line1" },
  { key: "hausnummer", label: "Hausnummer" },
  { key: "plz", label: "PLZ", auto: "postal-code" },
  { key: "ort", label: "Ort", auto: "address-level2" },
  { key: "telefon", label: "Telefon", auto: "tel" },
  { key: "email", label: "E-Mail", auto: "email" },
];

type Values = Record<string, string | boolean>;

export default function FormView({ documentId, onBack }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [info, setInfo] = useState<FormInfo | null>(null);
  const [profile, setProfile] = useState<Record<string, string>>({});
  const [values, setValues] = useState<Values>({});
  const [sources, setSources] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const i = await postFile<FormInfo>("/v1/forms", file);
      setInfo(i);
      const initial: Values = {};
      i.fields.forEach((f) => {
        if (f.value) initial[f.id] = f.type === "checkbox" ? true : f.value;
      });
      setValues(initial);
      setSources({});
      setNotes([]);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function suggest() {
    if (!info) return;
    setBusy(true);
    setError(null);
    try {
      const s = await postJson<FormSuggestions>(`/v1/forms/${info.form_id}/suggest`, { profile, document_id: documentId });
      const next = { ...values };
      const src: Record<string, string> = {};
      s.suggestions.forEach((x) => {
        if (!next[x.field_id]) next[x.field_id] = x.value;
        src[x.field_id] = x.source + (x.matched_by === "model" ? " · zugeordnet" : "");
      });
      setValues(next);
      setSources(src);
      setNotes(s.notes);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    if (!info) return;
    setBusy(true);
    setError(null);
    try {
      const payload: Values = {};
      Object.entries(values).forEach(([k, v]) => {
        if (v !== "" && v !== undefined) payload[k] = v;
      });
      const blob = await postForBlob(`/v1/forms/${info.form_id}/fill`, { values: payload });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = info.filename.replace(/\.pdf$/i, "") + "-ausgefuellt.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  function setValue(id: string, v: string | boolean) {
    setValues((prev) => ({ ...prev, [id]: v }));
  }

  function renderField(f: FormField) {
    const id = `field-${f.id}`;
    const source = sources[f.id];
    const head = (
      <span className="field-head">
        <span>{f.label}{f.required && <span className="req" aria-label="Pflichtfeld"> *</span>}</span>
        {source && <span className="pill">{source}</span>}
      </span>
    );
    if (f.type === "signature") {
      return <div key={f.id} className="field-sign">{head}<span className="card-note">Bitte selbst unterschreiben.</span></div>;
    }
    if (f.type === "checkbox") {
      return (
        <label key={f.id} className="field-check">
          <input type="checkbox" checked={values[f.id] === true} onChange={(e) => setValue(f.id, e.target.checked)} />
          {head}
        </label>
      );
    }
    if (f.type === "radio") {
      return (
        <fieldset key={f.id} className="field-radio">
          <legend>{head}</legend>
          {f.options.map((o) => (
            <label key={o.value}>
              <input type="radio" name={id} checked={values[f.id] === o.value} onChange={() => setValue(f.id, o.value)} />
              <span>{o.text}</span>
            </label>
          ))}
        </fieldset>
      );
    }
    if (f.type === "choice") {
      return (
        <label key={f.id} htmlFor={id}>
          {head}
          <select id={id} value={String(values[f.id] ?? "")} onChange={(e) => setValue(f.id, e.target.value)}>
            <option value="">Bitte wählen</option>
            {f.options.map((o) => <option key={o.value} value={o.value}>{o.text}</option>)}
          </select>
        </label>
      );
    }
    return (
      <label key={f.id} htmlFor={id}>
        {head}
        <input id={id} value={String(values[f.id] ?? "")} maxLength={f.max_length ?? undefined} onChange={(e) => setValue(f.id, e.target.value)} />
      </label>
    );
  }

  return (
    <main className="tool">
      <input ref={fileInput} className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={(e) => upload(e.target.files?.[0])} tabIndex={-1} aria-hidden="true" />
      <div className="tool-bar">
        <button type="button" className="link-button" onClick={onBack}>‹ Zurück</button>
        {info && <span className="pill">{info.filename}</span>}
      </div>
      <header className="tool-head">
        <h1>Formular ausfüllen.</h1>
        <p>Der Assistent trägt Ihre Angaben in die passenden Felder ein. Sie prüfen alles, dann laden Sie das PDF herunter. Nichts wird abgeschickt.</p>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      {!info ? (
        <section className="card dropzone">
          <p className="card-text">Laden Sie ein ausfüllbares PDF-Formular einer Behörde hoch.</p>
          <button type="button" className="button" disabled={busy} onClick={() => fileInput.current?.click()}>{busy ? "Wird gelesen …" : "PDF-Formular wählen"}</button>
        </section>
      ) : (
        <div className="tool-grid">
          <section className="card fields">
            <h2>Ihre Angaben</h2>
            <p className="card-note">Nur was Sie hier eintragen, wird verwendet. Die Angaben bleiben in diesem Fenster und werden nicht gespeichert.</p>
            <div className="profile-grid">
              {PROFILE.map((p) => (
                <label key={p.key}>
                  {p.label}
                  <input value={profile[p.key] ?? ""} autoComplete={p.auto} onChange={(e) => setProfile({ ...profile, [p.key]: e.target.value })} />
                </label>
              ))}
            </div>
            <button type="button" className="button" disabled={busy} onClick={suggest}>Felder vorschlagen</button>
          </section>

          <section className="card fields">
            <h2>Formularfelder <span className="optional">{info.fields.length}</span></h2>
            {info.warnings.map((w, i) => <p key={i} className="notice notice-warn">{w}</p>)}
            {notes.map((n, i) => <p key={i} className="notice">{n}</p>)}
            <div className="form-fields">{info.fields.map(renderField)}</div>
            {info.fields.length > 0 && (
              <div className="tool-actions">
                <button type="button" className="button" disabled={busy} onClick={download}>Ausgefülltes PDF herunterladen</button>
                <button type="button" className="link-button" onClick={() => fileInput.current?.click()}>Anderes Formular</button>
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
