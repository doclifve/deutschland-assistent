"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppointmentPlan, describeError, postJson } from "../lib/api";

type Props = {
  concern?: string;
  onBack: () => void;
};

const QUICK = [
  { id: "wohnsitz-anmelden", label: "Wohnsitz anmelden" },
  { id: "personalausweis", label: "Personalausweis" },
  { id: "reisepass", label: "Reisepass" },
  { id: "fuehrungszeugnis", label: "Führungszeugnis" },
  { id: "fahrzeug-zulassen", label: "Fahrzeug zulassen" },
];

export default function AppointmentView({ concern: initialConcern, onBack }: Props) {
  const [concern, setConcern] = useState(initialConcern ?? "");
  const [plz, setPlz] = useState("");
  const [plan, setPlan] = useState<AppointmentPlan | null>(null);
  const [done, setDone] = useState<Record<number, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function prepare(text: string, postal = plz) {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setPlan(await postJson<AppointmentPlan>("/v1/appointments/prepare", { concern: text, postal_code: postal || null }));
      setDone({});
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialConcern) prepare(initialConcern);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialConcern]);

  function submit(e: FormEvent) {
    e.preventDefault();
    prepare(concern);
  }

  return (
    <main className="tool">
      <div className="tool-bar">
        <button type="button" className="link-button" onClick={onBack}>‹ Zurück</button>
      </div>
      <header className="tool-head">
        <h1>Behördentermin.</h1>
        <p>Richtige Stelle, offizielle Buchungsseite, Unterlagen-Checkliste. Den Termin buchen Sie selbst.</p>
      </header>

      <div className="quick">
        {QUICK.map((q) => (
          <button key={q.id} type="button" className={plan?.concern_id === q.id ? "starter starter-on" : "starter"} onClick={() => { setConcern(q.label); prepare(q.id); }}>
            {q.label}
          </button>
        ))}
      </div>

      <form className="card fields fields-row" onSubmit={submit}>
        <label className="grow">Ihr Anliegen<input value={concern} onChange={(e) => setConcern(e.target.value)} placeholder="z. B. Ich bin umgezogen" /></label>
        <label className="narrow">Postleitzahl<input value={plz} onChange={(e) => setPlz(e.target.value.replace(/\D/g, "").slice(0, 5))} inputMode="numeric" autoComplete="postal-code" placeholder="20095" /></label>
        <button type="submit" className="button" disabled={busy || !concern.trim()}>Vorbereiten</button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}

      {plan && (
        <div className="plan">
          <section className="card">
            <div className="card-label">Zuständig</div>
            <h2 className="plan-title">{plan.title}</h2>
            <p className="card-text">{plan.office}</p>
            <div className="plan-links">
              {plan.links.filter((l) => l.kind !== "official_law").map((l, i) => (
                <a key={l.url} className={i === 0 ? "button plan-primary" : "source"} href={l.url} target="_blank" rel="noreferrer">
                  {i === 0 ? l.label : <><span className="source-title">{l.label}</span><span className="chevron" aria-hidden="true">›</span></>}
                </a>
              ))}
            </div>
          </section>

          {plan.bring.length > 0 && (
            <section className="card">
              <h2>Mitbringen</h2>
              <ul className="checklist">
                {plan.bring.map((b, i) => (
                  <li key={i}>
                    <label>
                      <input type="checkbox" checked={!!done[i]} onChange={(e) => setDone({ ...done, [i]: e.target.checked })} />
                      <span>{b}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="card">
            <h2>So geht es</h2>
            <ol className="steps">
              {plan.steps.map((s, i) => <li key={i}><span className="step-num" aria-hidden="true">{i + 1}</span><span>{s}</span></li>)}
            </ol>
            {plan.notes.map((n, i) => <p key={i} className="card-note">{n}</p>)}
            {plan.links.some((l) => l.kind === "official_law") && (
              <div className="chips">
                {plan.links.filter((l) => l.kind === "official_law").map((l) => <a key={l.url} className="chip" href={l.url} target="_blank" rel="noreferrer">{l.label}</a>)}
              </div>
            )}
          </section>

          {plan.alternatives.length > 0 && (
            <p className="card-note">Meinten Sie: {plan.alternatives.map((a, i) => (
              <span key={a.id}>{i > 0 && ", "}<button type="button" className="link-button inline" onClick={() => { setConcern(a.title); prepare(a.id); }}>{a.title}</button></span>
            ))}?</p>
          )}
          <p className="fine">{plan.disclaimer}</p>
        </div>
      )}
    </main>
  );
}
