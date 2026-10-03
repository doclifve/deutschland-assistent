"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Action, Answer, ChatMessage, ChatResponse, describeError, formatDate, postJson } from "../lib/api";

type Turn = { role: "user" | "assistant"; content: string; answer?: Answer; actions?: Action[] };

type Props = {
  documentId?: string;
  documentLabel?: string;
  initialQuestion?: string;
  onBack: () => void;
  onAction: (action: Action) => void;
};

const STARTERS = [
  "Was bedeutet § 60 SGB I?",
  "Ich bin umgezogen. Was muss ich tun?",
  "Wie lege ich Widerspruch ein?",
];

export default function ChatView({ documentId, documentLabel, initialQuestion, onBack, onAction }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const history: ChatMessage[] = [...turns.map((t) => ({ role: t.role, content: t.content })), { role: "user", content: message }];
    setTurns((t) => [...t, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const r = await postJson<ChatResponse>("/v1/chat", { messages: history.slice(-20), document_id: documentId });
      setTurns((t) => [...t, { role: "assistant", content: r.reply, answer: r.answer, actions: r.actions }]);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialQuestion && !started.current) {
      started.current = true;
      send(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  function submit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <main className="tool chat-view">
      <div className="tool-bar">
        <button type="button" className="link-button" onClick={onBack}>‹ Start</button>
        {documentLabel && <span className="pill">{documentLabel}</span>}
      </div>
      <header className="tool-head">
        <h1>Fragen.</h1>
        <p>Antworten mit amtlichen Quellen. Wenn es keine Quelle gibt, sage ich das.</p>
      </header>

      <div className="chat-log" aria-live="polite">
        {turns.length === 0 && !busy && (
          <div className="starters">
            {STARTERS.map((s) => (
              <button key={s} type="button" className="starter" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        {turns.map((t, i) =>
          t.role === "user" ? (
            <div key={i} className="bubble bubble-me">{t.content}</div>
          ) : (
            <div key={i} className="bubble bubble-bot">
              <p className="bubble-text">{t.answer?.what_does_it_mean ?? t.content}</p>
              {t.answer?.deadline && (
                <div className="bubble-deadline">
                  <span>Frist</span>
                  <strong>{formatDate(t.answer.deadline.date, { weekday: "short", day: "numeric", month: "short", year: "numeric" })}</strong>
                  {t.answer.deadline.confidence === "low" && <span className="pill pill-estimate">Geschätzt</span>}
                </div>
              )}
              {t.answer?.what_should_i_do && t.answer.what_should_i_do.length > 0 && (
                <ul className="bubble-steps">
                  {t.answer.what_should_i_do.slice(0, 4).map((s, j) => <li key={j}>{s}</li>)}
                </ul>
              )}
              {t.answer?.sources && t.answer.sources.filter((s) => s.url).length > 0 && (
                <div className="chips">
                  {t.answer.sources.filter((s) => s.url).slice(0, 4).map((s, j) => (
                    <a key={j} className="chip" href={s.url!} target="_blank" rel="noreferrer">{s.title}</a>
                  ))}
                </div>
              )}
              {t.actions && t.actions.length > 0 && (
                <div className="action-row">
                  {t.actions.map((a, j) => (
                    <button key={j} type="button" className="action" onClick={() => onAction(a)}>{a.label} ›</button>
                  ))}
                </div>
              )}
            </div>
          )
        )}
        {busy && (
          <div className="bubble bubble-bot typing" role="status" aria-label="Antwort wird erstellt">
            <i /><i /><i />
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        <div ref={endRef} />
      </div>

      <form className="ask chat-input" onSubmit={submit}>
        <label htmlFor="chat-input" className="visually-hidden">Ihre Frage</label>
        <input id="chat-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ihre Frage" autoComplete="off" />
        <button type="submit" className="button" disabled={!input.trim() || busy}>Senden</button>
      </form>
      <p className="fine">Informationshilfe, keine Rechtsberatung. Maßgeblich sind Originalbrief und amtliche Quellen.</p>
    </main>
  );
}
