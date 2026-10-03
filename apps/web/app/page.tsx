"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_CIVIC_API_URL || "http://localhost:8000";

type View = "home" | "loading" | "result";

type WhatsAppChannel = { enabled: boolean; display_number: string | null; link: string | null; greeting: string };

const DOC_TYPES: Record<string, string> = {
  authority_decision: "Bescheid",
  authority_request: "Aufforderung zur Mitwirkung",
  invoice: "Rechnung",
  contract_or_notice: "Vertrag oder Kündigung",
  unknown: "Schreiben",
};

const REQUIREMENT_KINDS: Record<string, string> = {
  document: "Unterlage",
  payment: "Zahlung",
  information: "Angabe",
};

const QUESTIONS = [
  { dot: "#000000", title: "Was ist das?", text: "Bescheid, Rechnung oder Aufforderung. Erkannt am Inhalt." },
  { dot: "#DD0000", title: "Was bedeutet das?", text: "Das Wichtigste aus dem Schreiben, klar zusammengefasst." },
  { dot: "#FFCC00", title: "Was muss ich tun?", text: "Die nächsten Schritte und welche Unterlagen verlangt werden." },
  { dot: "#000000", title: "Gibt es eine Frist?", text: "Ausdrückliche Daten und relative Fristen, nachvollziehbar berechnet." },
  { dot: "#DD0000", title: "Welches Gesetz gilt?", text: "Mit Link zur amtlichen Fassung." },
  { dot: "#FFCC00", title: "Was ist unklar?", text: "Offen benannt, statt geraten." },
];

function formatDate(iso: string, opts: Intl.DateTimeFormatOptions) {
  return new Date(iso + "T12:00:00").toLocaleDateString("de-DE", opts);
}

function Logo({ size = "hero" }: { size?: "hero" | "small" }) {
  return (
    <div
      className={`logo logo-${size}`}
      role="img"
      aria-label="Drei Kreise in Schwarz, Rot und Gold, die atmen und sich langsam drehen"
    >
      <div className="logo-scale">
        <div className="logo-cluster">
          <span className="logo-c logo-top" />
          <span className="logo-c logo-left" />
          <span className="logo-c logo-right" />
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [view, setView] = useState<View>("home");
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [doc, setDoc] = useState<any>(null);
  const [question, setQuestion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const howRef = useRef<HTMLElement>(null);
  const [whatsapp, setWhatsapp] = useState<WhatsAppChannel | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<Array<{role:"user"|"assistant";content:string}>>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [appointmentService, setAppointmentService] = useState("");
  const [appointmentLocation, setAppointmentLocation] = useState("");
  const [appointmentUrl, setAppointmentUrl] = useState("");
  const [appointmentAction, setAppointmentAction] = useState<any>(null);
  const formAgentInput = useRef<HTMLInputElement>(null);
  const [formInspection, setFormInspection] = useState<any>(null);
  const [formProfile, setFormProfile] = useState("");
  const [formAction, setFormAction] = useState<any>(null);

  // Public channel details come from the API; the section only shows when a number is configured.
  useEffect(() => {
    let cancelled = false;
    fetch(API + "/v1/channels")
      .then((r) => (r.ok ? r.json() : null))
      .then(async (data) => {
        const wa: WhatsAppChannel | undefined = data?.whatsapp;
        if (cancelled || !wa?.enabled || !wa.link) return;
        setWhatsapp(wa);
        const QRCode = (await import("qrcode")).default;
        const url = await QRCode.toDataURL(wa.link, { margin: 1, width: 560, color: { dark: "#1D1D1F", light: "#FFFFFF" } });
        if (!cancelled) setQr(url);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  async function askApi(message: string, documentId?: string) {
    const r = await fetch(API + "/v1/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, language: "de", document_id: documentId }),
    });
    if (!r.ok) throw new Error(r.status === 404 ? "Das Dokument ist abgelaufen. Bitte erneut hochladen." : await r.text());
    return r.json();
  }

  function fail(e: unknown) {
    const msg = e instanceof TypeError
      ? `Keine Verbindung zum Backend unter ${API}. Läuft es?`
      : String(e instanceof Error ? e.message : e);
    setError(msg);
    setView("home");
    window.scrollTo({ top: 0 });
  }

  async function upload(file?: File) {
    if (!file) return;
    setError(null);
    setView("loading");
    try {
      const f = new FormData();
      f.append("file", file);
      const r = await fetch(API + "/v1/documents", { method: "POST", body: f });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setDoc(d);
      setQuestion(null);
      setAnswer(await askApi("Was bedeutet das und was muss ich tun?", d.document_id));
      setView("result");
      window.scrollTo({ top: 0 });
    } catch (e) {
      fail(e);
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function ask(e: FormEvent) {
    e.preventDefault();
    const message = q.trim();
    if (!message) return;
    setError(null);
    setView("loading");
    try {
      const docId = view === "result" && doc ? doc.document_id : undefined;
      if (!docId) setDoc(null);
      setAnswer(await askApi(message, docId));
      setQuestion(message);
      setQ("");
      setView("result");
      window.scrollTo({ top: 0 });
    } catch (err) {
      fail(err);
    }
  }


  async function chatSubmit(e: FormEvent) {
    e.preventDefault();
    const message = chatInput.trim();
    if (!message || chatBusy) return;
    const next = [...chatMessages, { role: "user" as const, content: message }];
    setChatMessages(next);
    setChatInput("");
    setChatBusy(true);
    try {
      const r = await fetch(API + "/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next, language: "de" }),
      });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      setChatMessages([...next, { role: "assistant", content: data.message }]);
    } catch (e) {
      setChatMessages([...next, { role: "assistant", content: String(e instanceof Error ? e.message : e) }]);
    } finally {
      setChatBusy(false);
    }
  }

  async function prepareAppointment(e: FormEvent) {
    e.preventDefault();
    const r = await fetch(API + "/v1/actions/appointment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service: appointmentService,
        location: appointmentLocation || null,
        official_booking_url: appointmentUrl || null,
      }),
    });
    if (!r.ok) throw new Error(await r.text());
    setAppointmentAction(await r.json());
  }

  async function confirmAppointment(approve: boolean) {
    if (!appointmentAction) return;
    const r = await fetch(API + `/v1/actions/${appointmentAction.action_id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve, expected_version: appointmentAction.version }),
    });
    if (!r.ok) throw new Error(await r.text());
    setAppointmentAction(await r.json());
  }

  async function inspectAgentForm(file?: File) {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(API + "/v1/forms/inspect", { method: "POST", body: fd });
    if (!r.ok) throw new Error(await r.text());
    setFormInspection(await r.json());
    setFormAction(null);
  }

  function profileFromText(text: string) {
    const profile: Record<string, string> = {};
    text.split(/\n+/).forEach((line) => {
      const i = line.indexOf(":");
      if (i > 0) {
        const key = line.slice(0, i).trim();
        const value = line.slice(i + 1).trim();
        if (key && value) profile[key] = value;
      }
    });
    return profile;
  }

  async function prepareAgentForm() {
    if (!formInspection) return;
    const profile = profileFromText(formProfile);
    const r = await fetch(API + `/v1/forms/${formInspection.form_id}/agent-prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile }),
    });
    if (!r.ok) throw new Error(await r.text());
    setFormAction(await r.json());
  }

  async function confirmAgentForm() {
    if (!formAction) return;
    const r = await fetch(API + `/v1/actions/${formAction.action_id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approve: true, expected_version: formAction.version }),
    });
    if (!r.ok) throw new Error(await r.text());
    setFormAction(await r.json());
  }

  function reset() {
    setView("home");
    setAnswer(null);
    setDoc(null);
    setQuestion(null);
    setError(null);
    window.scrollTo({ top: 0 });
  }

  const fileField = (
    <input
      ref={fileInput}
      className="visually-hidden"
      type="file"
      accept=".pdf,.txt,.md,.png,.jpg,.jpeg,.webp,.tif,.tiff,image/*"
      onChange={(e) => upload(e.target.files?.[0])}
      tabIndex={-1}
      aria-hidden="true"
    />
  );

  if (view === "loading") {
    return (
      <main className="screen center" aria-busy="true">
        <Logo />
        <p className="loading-text" role="status">Wird gelesen …</p>
      </main>
    );
  }

  if (view === "result" && answer) {
    const deadline = answer.deadline;
    const title = doc ? DOC_TYPES[doc.document_type] || "Schreiben" : "Ihre Frage";
    const subtitle = doc
      ? [doc.authority_hint, doc.document_date && `Brief vom ${formatDate(doc.document_date, { day: "numeric", month: "short", year: "numeric" })}`]
          .filter(Boolean)
          .join(" · ") || doc.filename
      : question;
    const steps: string[] = answer.what_should_i_do || [];
    const sources: any[] = (answer.sources || []).filter((s: any) => s.url);

    return (
      <main className="result">
        {fileField}
        <div className="result-inner">
          <div className="result-bar">
            <button type="button" className="link-button" onClick={reset}>‹ Start</button>
            {doc && (
              <button type="button" className="link-button" onClick={() => fileInput.current?.click()}>
                Anderer Brief
              </button>
            )}
          </div>

          <header className="result-head">
            {subtitle && <div className="result-sub">{subtitle}</div>}
            <h1>{title}</h1>
          </header>

          {deadline && (
            <section className="card">
              <div className="card-row">
                <div className="card-label">
                  {answer.appeal_instruction?.remedy === "widerspruch" ? "Widerspruch möglich bis" :
                   answer.appeal_instruction?.remedy === "einspruch" ? "Einspruch möglich bis" : "Frist"}
                </div>
                {deadline.confidence === "low" && <span className="pill pill-estimate">Geschätzt</span>}
              </div>
              <div className="deadline-date">
                {formatDate(deadline.date, { weekday: "short", day: "numeric", month: "short" })}
              </div>
              <div className="card-note">
                {deadline.confidence === "low"
                  ? "Berechnet ab Briefdatum. Maßgeblich ist, wann der Brief tatsächlich ankam."
                  : formatDate(deadline.date, { day: "numeric", month: "long", year: "numeric" })}
              </div>
              {answer.relative_deadlines?.length > 0 && (
                <details className="basis">
                  <summary>Wie wurde das berechnet?</summary>
                  <ul>
                    {answer.relative_deadlines
                      .flatMap((r: any) => [r.raw, ...(r.basis || [])])
                      .map((x: string, i: number) => <li key={i}>{x}</li>)}
                  </ul>
                </details>
              )}
            </section>
          )}

          <section className="card">
            <h2>Was bedeutet das?</h2>
            <p className="card-text">{answer.what_does_it_mean}</p>
          </section>

          {answer.requirements?.length > 0 && (
            <section className="card">
              <h2>Was verlangt wird</h2>
              <ul className="rows">
                {answer.requirements.map((r: any, i: number) => (
                  <li key={i} className="row">
                    <span>{r.text}</span>
                    <span className="pill">{REQUIREMENT_KINDS[r.kind] || "Aufgabe"}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {answer.appeal_instruction && (
            <section className="card">
              <h2>{answer.appeal_instruction.remedy === "unknown" ? "Rechtsbehelf" : String(answer.appeal_instruction.remedy).replace(/^./, (c: string) => c.toUpperCase())}</h2>
              {answer.appeal_instruction.deadline_expression && <p className="card-text">{answer.appeal_instruction.deadline_expression}</p>}
              {answer.appeal_instruction.recipient && <p className="card-text">An: {answer.appeal_instruction.recipient}</p>}
              {answer.appeal_instruction.methods?.length > 0 && <p className="card-text">Wege: {answer.appeal_instruction.methods.join(", ")}</p>}
            </section>
          )}

          {steps.length > 0 && (
            <section className="card">
              <h2>Was ist zu tun?</h2>
              <ol className="steps">
                {steps.map((x, i) => (
                  <li key={i}><span className="step-num" aria-hidden="true">{i + 1}</span><span>{x}</span></li>
                ))}
              </ol>
            </section>
          )}

          {sources.length > 0 && (
            <section className="card card-list">
              <h2 className="visually-hidden">Amtliche Quellen</h2>
              {sources.map((s, i) => (
                <a key={i} href={s.url} target="_blank" rel="noreferrer" className="source">
                  <span>
                    <span className="source-title">{s.title}</span>
                    <span className="source-meta">
                      {s.kind === "official_case_law" ? "Rechtsprechung" : s.authority}
                    </span>
                  </span>
                  <span className="chevron" aria-hidden="true">›</span>
                </a>
              ))}
            </section>
          )}

          {answer.warnings?.length > 0 && (
            <section className="card card-quiet">
              <ul className="warnings">{answer.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}</ul>
            </section>
          )}

          <form className="ask ask-inline" onSubmit={ask}>
            <label htmlFor="followup" className="visually-hidden">Weitere Frage</label>
            <input
              id="followup"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={doc ? "Weitere Frage zu diesem Brief" : "Weitere Frage"}
            />
            <button type="submit" className="button" disabled={!q.trim()}>Fragen</button>
          </form>

          <p className="fine">{answer.disclaimer}</p>
        </div>
      </main>
    );
  }

  return (
    <main>
      {fileField}

      <section className="screen hero">
        <div className="wordmark">Deutschland Assistent</div>
        <Logo />
        <h1 className="hero-title">Behördenpost. <br className="phone-break" />Endlich verständlich.</h1>
        <p className="hero-sub">Brief fotografieren. Verstehen, was drinsteht. Wissen, was zu tun ist.</p>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="hero-spacer" />
        <div className="hero-actions">
          <button type="button" className="button button-wide" onClick={() => fileInput.current?.click()}>
            Brief fotografieren
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() => howRef.current?.scrollIntoView({ behavior: "smooth" })}
          >
            So funktioniert’s ›
          </button>
        </div>
      </section>

      <section className="section" ref={howRef}>
        <h2 className="section-title">So einfach.</h2>
        <p className="section-sub">Drei Schritte vom Brief zur Klarheit.</p>
        <div className="steps-big">
          <div className="step-big">
            <span className="step-icon" style={{ background: "#000000" }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></svg>
            </span>
            <div><h3>Fotografieren.</h3><p>Brief, Bescheid oder PDF. Einfach hochladen.</p></div>
          </div>
          <div className="step-big">
            <span className="step-icon" style={{ background: "#DD0000" }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 3h9l3 3v15H6z" /><path d="M9 11h6M9 15h6M9 7h3" /></svg>
            </span>
            <div><h3>Verstehen.</h3><p>Was ist das? Was bedeutet es? Klar zusammengefasst.</p></div>
          </div>
          <div className="step-big">
            <span className="step-icon" style={{ background: "#FFCC00" }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M4 10h16M8 3v4M16 3v4M9 15l2 2 4-4" /></svg>
            </span>
            <div><h3>Handeln.</h3><p>Frist, nächste Schritte, nötige Unterlagen. Mit amtlicher Quelle.</p></div>
          </div>
        </div>
      </section>

      <section className="section section-grey">
        <p className="section-eyebrow">Eine Antwort auf jeden Brief.</p>
        <h2 className="section-title">Sechs Fragen. Klar beantwortet.</h2>
        <div className="question-grid">
          {QUESTIONS.map((x) => (
            <div className="question" key={x.title}>
              <span className="dot" style={{ background: x.dot }} />
              <h3>{x.title}</h3>
              <p>{x.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Die Quelle zählt.<br /><span className="muted-title">Nicht das Modell.</span></h2>
        <div className="trust">
          <div>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 19V6a2 2 0 0 1 2-2h12v15H6a2 2 0 0 0-2 2z" /><path d="M9 8h6M9 12h4" /></svg>
            <h3>Amtliche Quellen.</h3>
            <p>Jede Antwort verweist auf Gesetze im Internet, NeuRIS oder das Bundesportal.</p>
          </div>
          <div>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#DD0000" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></svg>
            <h3>Nichts bleibt liegen.</h3>
            <p>Ihre Dokumente werden nach spätestens einer Stunde gelöscht.</p>
          </div>
          <div>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#B38F00" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M8 7l-5 5 5 5M16 7l5 5-5 5M13.5 5l-3 14" /></svg>
            <h3>Offen für alle.</h3>
            <p>Open Source. Werbefrei. Ohne Konto.</p>
          </div>
        </div>
      </section>

      {whatsapp?.link && (
        <section className="section whatsapp" id="whatsapp">
          <div className="whatsapp-grid">
            <div>
              <span className="whatsapp-icon" aria-hidden="true">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M20 11.5a8 8 0 0 1-11.6 7.1L4 20l1.4-4.2A8 8 0 1 1 20 11.5z" /><path d="M9 10h6M9 13.5h4" /></svg>
              </span>
              <h2 className="section-title">Einfach per WhatsApp.</h2>
              <p className="section-sub">Brief fotografieren, in den Chat schicken. Die Antwort kommt direkt zurück.</p>
              <ol className="whatsapp-steps">
                <li><span className="step-num" style={{ background: "#000000" }}>1</span><span><strong>Chat öffnen.</strong> WhatsApp startet mit unserer Nummer.</span></li>
                <li><span className="step-num" style={{ background: "#DD0000" }}>2</span><span><strong>Foto schicken.</strong> Brief oder PDF, gern mit einer Frage.</span></li>
                <li><span className="step-num step-num-gold">3</span><span><strong>Antwort lesen.</strong> Frist, nächste Schritte und amtliche Quellen.</span></li>
              </ol>
              <a className="button whatsapp-button" href={whatsapp.link} target="_blank" rel="noreferrer">In WhatsApp öffnen</a>
              <p className="whatsapp-fine">
                Nachrichten laufen über WhatsApp (Meta). Ihre Dokumente löschen wir nach spätestens einer Stunde.
              </p>
            </div>
            <div className="whatsapp-qr">
              {qr ? (
                <img src={qr} width={280} height={280} alt={`QR-Code: WhatsApp-Chat mit ${whatsapp.display_number}`} />
              ) : (
                <div className="qr-placeholder" aria-hidden="true" />
              )}
              <p className="qr-caption">Mit der Handykamera scannen</p>
              <p className="qr-number">{whatsapp.display_number}</p>
            </div>
          </div>
        </section>
      )}


      <section className="section section-grey" id="assistant-chat">
        <p className="section-eyebrow">Der Assistent</p>
        <h2 className="section-title">Schreiben. Fragen. Erledigen.</h2>
        <p className="section-sub">
          Mit konfiguriertem Deutschland-LLM können Sie frei schreiben. Bei Behörden- und Rechtsfragen
          werden amtliche Quellen eingebunden.
        </p>
        <div className="agent-grid">
          <div className="agent-card">
            <h3>Mit dem Assistenten schreiben</h3>
            <div className="chat-box" aria-live="polite">
              {chatMessages.length === 0 && <p className="agent-muted">Fragen Sie zum Beispiel: „Welche Unterlagen brauche ich für einen neuen Personalausweis?“</p>}
              {chatMessages.map((m, i) => (
                <div key={i} className={`chat-message chat-${m.role}`}>{m.content}</div>
              ))}
            </div>
            <form className="agent-form" onSubmit={chatSubmit}>
              <input value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="Nachricht schreiben …" />
              <button className="button" type="submit" disabled={!chatInput.trim() || chatBusy}>
                {chatBusy ? "Denkt …" : "Senden"}
              </button>
            </form>
          </div>

          <div className="agent-card">
            <h3>Termin vorbereiten</h3>
            <p className="agent-muted">Der Assistent bereitet die Aktion vor. Gebucht wird erst nach Ihrer Bestätigung und nur über einen freigegebenen Connector.</p>
            <form className="agent-form agent-form-stack" onSubmit={prepareAppointment}>
              <input value={appointmentService} onChange={(e) => setAppointmentService(e.target.value)} placeholder="z. B. Personalausweis beantragen" required />
              <input value={appointmentLocation} onChange={(e) => setAppointmentLocation(e.target.value)} placeholder="Ort / Behörde (optional)" />
              <input value={appointmentUrl} onChange={(e) => setAppointmentUrl(e.target.value)} placeholder="Offizielle Buchungs-URL (optional)" />
              <button className="button" type="submit" disabled={!appointmentService.trim()}>Vorschau erstellen</button>
            </form>
            {appointmentAction && (
              <div className="action-preview">
                <strong>{appointmentAction.summary}</strong>
                <p>Status: {appointmentAction.status}</p>
                {appointmentAction.status === "prepared" && (
                  <div className="action-buttons">
                    <button className="button" type="button" onClick={() => confirmAppointment(true)}>Bestätigen</button>
                    <button className="link-button" type="button" onClick={() => confirmAppointment(false)}>Abbrechen</button>
                  </div>
                )}
                {appointmentAction.status === "approved" && <p>Freigegeben. Ein verbundener Browser-/Behörden-Connector darf den Termin jetzt ausführen.</p>}
              </div>
            )}
          </div>

          <div className="agent-card">
            <h3>PDF-Formular ausfüllen</h3>
            <p className="agent-muted">Ausfüllbares PDF hochladen. Der Formular-Agent ordnet Ihre Angaben den vorhandenen Feldern zu. Das PDF wird erst nach Bestätigung erzeugt.</p>
            <input ref={formAgentInput} className="visually-hidden" type="file" accept=".pdf,application/pdf" onChange={(e) => inspectAgentForm(e.target.files?.[0])} />
            <button className="button" type="button" onClick={() => formAgentInput.current?.click()}>Formular auswählen</button>
            {formInspection && (
              <div className="form-agent">
                <p>{formInspection.fields.length} ausfüllbare Felder erkannt.</p>
                <textarea
                  value={formProfile}
                  onChange={(e) => setFormProfile(e.target.value)}
                  placeholder={"Vorname: Max\nNachname: Mustermann\nGeburtsdatum: 01.01.1990\nStraße: Musterstraße 1\nPLZ: 12345\nOrt: Berlin"}
                  rows={7}
                />
                <button className="button" type="button" onClick={prepareAgentForm} disabled={!formProfile.trim()}>Agent Vorschau erstellen</button>
              </div>
            )}
            {formAction && (
              <div className="action-preview">
                <strong>{formAction.summary}</strong>
                <p>{Object.keys(formAction.payload?.values || {}).length} Felder werden ausgefüllt.</p>
                {formAction.payload?.unresolved?.length > 0 && <p>Noch unklar: {formAction.payload.unresolved.join(", ")}</p>}
                {formAction.status === "prepared" && <button className="button" type="button" onClick={confirmAgentForm}>Ausfüllen bestätigen</button>}
                {formAction.status === "completed" && formAction.artifact_url && (
                  <a className="button" href={API + formAction.artifact_url}>Ausgefülltes PDF herunterladen</a>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="section section-grey section-ask">
        <h2 className="section-title">Oder einfach fragen.</h2>
        <form className="ask" onSubmit={ask}>
          <label htmlFor="question" className="visually-hidden">Ihre Frage</label>
          <input
            id="question"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="z. B. Was bedeutet § 60 SGB I?"
          />
          <button type="submit" className="button" disabled={!q.trim()}>Fragen</button>
        </form>
        <p className="fine">Informationshilfe, keine Rechtsberatung. Maßgeblich sind Originalbrief und amtliche Quellen.</p>
      </section>
    </main>
  );
}
