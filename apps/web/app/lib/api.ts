export const API = process.env.NEXT_PUBLIC_CIVIC_API_URL || "http://localhost:8000";

export type Link = { label: string; url: string; kind: string };
export type Action = { kind: "letter" | "appointment" | "form"; label: string; params: Record<string, string> };
export type ChatMessage = { role: "user" | "assistant"; content: string };
export type Source = { title: string; url?: string | null; authority?: string; kind?: string };

export type Answer = {
  what_is_this?: string | null;
  what_does_it_mean: string;
  what_should_i_do?: string[];
  deadline?: { date: string; label: string; confidence: "high" | "medium" | "low" } | null;
  relative_deadlines?: { raw: string; basis?: string[] }[];
  requirements?: { text: string; kind: string }[];
  appeal_instruction?: { remedy: string; deadline_expression?: string | null; recipient?: string | null; methods?: string[] } | null;
  sources?: Source[];
  warnings?: string[];
  disclaimer: string;
};

export type ChatResponse = { reply: string; answer: Answer; actions: Action[] };

export type AppointmentPlan = {
  concern_id: string | null;
  title: string;
  office: string;
  steps: string[];
  bring: string[];
  links: Link[];
  notes: string[];
  alternatives: { id: string; title: string }[];
  disclaimer: string;
};

export type LetterKind = "widerspruch" | "fristverlaengerung" | "nachreichung";

export type LetterDraft = {
  kind: LetterKind;
  title: string;
  sender_block: string;
  recipient_block: string;
  place_date: string;
  subject: string;
  body: string;
  full_text: string;
  missing: string[];
  notes: string[];
  warnings: string[];
  legal: Link[];
};

export type FormField = {
  id: string;
  type: "text" | "checkbox" | "radio" | "choice" | "signature" | "unknown";
  label: string;
  page?: number | null;
  value?: string | null;
  options: { value: string; text: string }[];
  checked_value?: string | null;
  required: boolean;
  max_length?: number | null;
};

export type FormInfo = { form_id: string; filename: string; pages: number; fields: FormField[]; warnings: string[] };
export type FormSuggestions = {
  form_id: string;
  suggestions: { field_id: string; value: string; source: string; matched_by: string }[];
  unfilled: string[];
  notes: string[];
};

export class ApiError extends Error {}

async function handle<T>(r: Response): Promise<T> {
  if (r.ok) return r.json() as Promise<T>;
  let detail = "";
  try {
    const body = await r.json();
    detail = typeof body?.detail === "string" ? body.detail : "";
  } catch {
    /* not JSON */
  }
  if (r.status === 404) throw new ApiError(detail || "Nicht mehr verfügbar. Bitte erneut hochladen.");
  throw new ApiError(detail || `Fehler ${r.status}`);
}

export function describeError(e: unknown): string {
  if (e instanceof TypeError) return `Keine Verbindung zum Backend unter ${API}. Läuft es?`;
  return e instanceof Error ? e.message : String(e);
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return handle<T>(r);
}

export async function postFile<T>(path: string, file: File): Promise<T> {
  const f = new FormData();
  f.append("file", file);
  return handle<T>(await fetch(API + path, { method: "POST", body: f }));
}

export async function postForBlob(path: string, body: unknown): Promise<Blob> {
  const r = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) await handle(r);
  return r.blob();
}

export function formatDate(iso: string, opts: Intl.DateTimeFormatOptions) {
  return new Date(iso + "T12:00:00").toLocaleDateString("de-DE", opts);
}
