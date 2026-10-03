from __future__ import annotations

import os
import threading
import time
import uuid

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .appointments import prepare_appointment
from .channels import channels_info
from .chat import compose_reply, detect_actions, last_user_message, model_question, retrieval_query
from .forms import FormError, FormStore, SuggestContext, fill_form, read_form, suggest_by_label, suggest_by_model
from .letters import draft_letter, extract_reference
from .documents import DocumentParseError, parse_document
from .evidence import EvidenceEngine
from .answer_generation import generate_grounded_explanation
from .model_provider import ModelProviderError, build_model_provider
from .extraction import (
    classify_document,
    extract_appeal_instruction,
    extract_authority_hint,
    extract_deadlines,
    extract_document_date,
    extract_leika_ids,
    extract_legal_references,
    extract_relative_deadlines,
    extract_requested_items,
    extract_requirements,
)
from .schemas import (
    AppointmentPlan,
    AppointmentRequest,
    AskRequest,
    ChatRequest,
    ChatResponse,
    FormFillRequest,
    FormInfo,
    FormSuggestions,
    FormSuggestRequest,
    LetterDraft,
    LetterRequest,
    ChannelsInfo,
    CivicAnswer,
    Deadline,
    DocumentAnalysis,
    EvidenceBundle,
    EvidenceSearchRequest,
    RelativeDeadline,
)

VERSION = "0.2.5"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_DOCUMENT_PAGES = int(os.getenv("MAX_DOCUMENT_PAGES", "30"))
DOCUMENT_ENGINE = os.getenv("DOCUMENT_ENGINE", "auto")
DOCUMENT_TTL_SECONDS = int(os.getenv("DOCUMENT_TTL_SECONDS", "3600"))
MAX_STORED_DOCUMENTS = int(os.getenv("MAX_STORED_DOCUMENTS", "500"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]


class DocumentStore:
    """Ephemeral in-memory store. Documents expire after a TTL and the store is size-capped."""

    def __init__(self, ttl: int, max_items: int):
        self.ttl = ttl
        self.max_items = max_items
        self._items: dict[str, tuple[float, str, DocumentAnalysis]] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for key in [k for k, (created, _, _) in self._items.items() if now - created > self.ttl]:
            del self._items[key]
        while len(self._items) > self.max_items:
            del self._items[min(self._items, key=lambda k: self._items[k][0])]

    def put(self, doc_id: str, text: str, analysis: DocumentAnalysis) -> None:
        with self._lock:
            now = time.monotonic()
            self._items[doc_id] = (now, text, analysis)
            self._purge(now)

    def get(self, doc_id: str) -> tuple[str, DocumentAnalysis] | None:
        with self._lock:
            self._purge(time.monotonic())
            item = self._items.get(doc_id)
            return (item[1], item[2]) if item else None

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            return self._items.pop(doc_id, None) is not None

    def __len__(self) -> int:
        return len(self._items)


STORE = DocumentStore(DOCUMENT_TTL_SECONDS, MAX_STORED_DOCUMENTS)
FORMS = FormStore(DOCUMENT_TTL_SECONDS, MAX_STORED_DOCUMENTS)
engine = EvidenceEngine()
model_provider = build_model_provider()


def primary_deadline(deadlines: list[Deadline], relative: list[RelativeDeadline]) -> Deadline | None:
    if deadlines:
        return min(deadlines, key=lambda d: d.date)
    estimated = [r for r in relative if r.estimated_end]
    if estimated:
        r = min(estimated, key=lambda r: r.estimated_end)
        return Deadline(
            date=r.estimated_end,
            label=f"Geschätztes Fristende ({r.raw})",
            confidence="low",
            evidence_text=r.raw,
        )
    return None


app = FastAPI(
    title="Deutschland Assistent API",
    version=VERSION,
    description="Evidence-first civic assistance core for Germany.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "deutschland-assistent-core", "version": VERSION}


@app.get("/v1/channels", response_model=ChannelsInfo)
def channels():
    """Public connection details for messaging channels (currently WhatsApp)."""
    return channels_info()


@app.get("/v1/sources")
def sources():
    return {
        "sources": [
            {
                "id": "gesetze-im-internet",
                "authority": "BMJ/BfJ",
                "role": "exact legal-reference fallback",
                "status": "authoritative",
            },
            {
                "id": "neuris",
                "authority": "BMJ/BfJ / DigitalService",
                "role": "federal legislation and case-law search",
                "status": "official-testphase-incomplete",
            },
            {
                "id": "bundesportal",
                "authority": "Bundesportal and federal agencies",
                "role": "public-service and benefit guidance",
                "status": "authoritative-curated",
            },
            {
                "id": "docling",
                "authority": "local document engine",
                "role": "OCR/layout parsing for scans and images",
                "status": "enabled-in-production-image",
            },
        ]
    }


@app.post("/v1/documents", response_model=DocumentAnalysis)
async def documents(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Leere Datei.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei ist zu groß.")

    filename = file.filename or "document"
    try:
        parsed = await run_in_threadpool(
            parse_document,
            data,
            filename,
            DOCUMENT_ENGINE,
            max_pages=MAX_DOCUMENT_PAGES,
            max_file_size=MAX_UPLOAD_BYTES,
        )
    except DocumentParseError as exc:
        raise HTTPException(415, str(exc)) from exc

    text = parsed.text
    doc_id = "doc_" + uuid.uuid4().hex[:16]
    doc_date = extract_document_date(text)
    relative = extract_relative_deadlines(text, doc_date)
    requirements = extract_requirements(text)
    appeal = extract_appeal_instruction(text)
    rel_warn = ["Frist ist relativ formuliert, aber das Datum des Schreibens wurde nicht erkannt."] if relative and not doc_date else []

    analysis = DocumentAnalysis(
        document_id=doc_id,
        filename=filename,
        document_type=classify_document(text),
        parsing_engine=parsed.engine,
        text_preview=" ".join(text.split())[:3500],
        document_date=doc_date,
        deadlines=extract_deadlines(text, doc_date),
        relative_deadlines=relative,
        legal_references=extract_legal_references(text),
        leika_ids=extract_leika_ids(text),
        authority_hint=extract_authority_hint(text),
        requested_items=extract_requested_items(text),
        requirements=requirements,
        appeal_instruction=appeal,
        warnings=parsed.warnings + rel_warn + ([] if text.strip() else ["Kein verwertbarer Text erkannt."]),
    )
    STORE.put(doc_id, text, analysis)
    return analysis


@app.delete("/v1/documents/{document_id}", status_code=204)
def delete_document(document_id: str):
    if not STORE.delete(document_id):
        raise HTTPException(404, "Dokument nicht gefunden.")
    return Response(status_code=204)


@app.post("/v1/evidence/search", response_model=EvidenceBundle)
async def evidence_search(req: EvidenceSearchRequest):
    return await engine.collect(
        req.query,
        extract_legal_references(req.query),
        extract_leika_ids(req.query),
        req.limit,
        include_case_law=req.include_case_law,
    )


def _stored_document(document_id: str | None) -> tuple[str, DocumentAnalysis] | None:
    if not document_id:
        return None
    stored = STORE.get(document_id)
    if not stored:
        raise HTTPException(404, "Dokument nicht gefunden oder bereits gelöscht.")
    return stored


@app.post("/v1/ask", response_model=CivicAnswer)
async def ask(req: AskRequest):
    return await build_answer(req.message, req.document_id)


async def build_answer(
    message: str,
    document_id: str | None,
    *,
    model_question_text: str | None = None,
    search_text: str | None = None,
) -> CivicAnswer:
    """Evidence-bound answer. Shared by /v1/ask and /v1/chat."""
    text = search_text or message
    analysis = None
    stored = _stored_document(document_id)
    if stored:
        text, analysis = stored

    refs = analysis.legal_references if analysis else extract_legal_references(text)
    deadlines = analysis.deadlines if analysis else extract_deadlines(text)
    relative = analysis.relative_deadlines if analysis else extract_relative_deadlines(text)
    leika = analysis.leika_ids if analysis else extract_leika_ids(text)
    requirements = analysis.requirements if analysis else extract_requirements(text)
    appeal = analysis.appeal_instruction if analysis else extract_appeal_instruction(text)
    deadline = primary_deadline(deadlines, relative)

    query = (
        (search_text or message)
        if not analysis
        else " ".join(
            x
            for x in [
                analysis.authority_hint or "",
                " ".join(r.raw for r in refs),
                analysis.document_type.replace("_", " "),
                appeal.remedy if appeal else "",
                search_text or message,
            ]
            if x
        )
    )
    bundle = await engine.collect(
        query[:1800],
        refs,
        leika,
        12,
        include_case_law=bool(refs or appeal),
    )

    grounded_warning: list[str] = []
    generated_meaning: str | None = None
    try:
        generated_meaning = await generate_grounded_explanation(
            model_provider,
            question=model_question_text or message,
            analysis=analysis,
            bundle=bundle,
        )
    except ModelProviderError as exc:
        grounded_warning.append(f"Sprachmodell-Fallback aktiv: {exc}")

    if analysis:
        meaning = generated_meaning or (
            "Das Dokument wurde gelesen und mit amtlichen Quellen abgeglichen. "
            "Fristen, Forderungen und Rechtsbehelfsangaben werden getrennt ausgewiesen."
        )
        steps: list[str] = []
        if deadlines or relative:
            steps.append("Prüfen Sie die erkannte Frist im Originaldokument.")
        if requirements:
            steps.append("Arbeiten Sie die erkannten Anforderungen einzeln ab und prüfen Sie sie am Originaltext.")
        if appeal:
            steps.append(
                f"Wenn Sie den Bescheid angreifen möchten, prüfen Sie die erkannte {appeal.remedy.title()}-Belehrung besonders sorgfältig."
            )
        if refs:
            steps.append("Vergleichen Sie die genannten Rechtsgrundlagen mit den verlinkten amtlichen Fassungen.")
        if not steps:
            steps.append("Prüfen Sie Absender, Anliegen und eventuell verlangte nächste Schritte im Original.")
        certainty = "high" if deadlines or refs or requirements or appeal else "medium"
    elif refs:
        meaning = generated_meaning or (
            "Ich habe ein konkretes Gesetzeszitat erkannt und mit amtlichen Rechtsquellen verknüpft. "
            "Zusätzlich kann passende Rechtsprechung angezeigt werden."
        )
        steps = [
            "Öffnen Sie die amtliche Fassung der Norm.",
            "Prüfen Sie Rechtsprechung nur im Kontext des konkreten Sachverhalts.",
        ]
        certainty = "high"
    else:
        meaning = generated_meaning or (
            "Ich habe amtliche Quellen zu Ihrer Frage gesucht. Die Treffer dienen als nachvollziehbare Grundlage; "
            "eine individuelle Rechtsfolge wird daraus nicht automatisch abgeleitet."
        )
        steps = [
            "Öffnen Sie die relevantesten amtlichen Quellen.",
            "Laden Sie ein Schreiben hoch, wenn sich die Frage auf einen konkreten Bescheid oder Brief bezieht.",
        ]
        certainty = "medium" if bundle.items else "low"

    if deadline and deadline.confidence == "low":
        steps.insert(0, "Das Fristende ist geschätzt. Notieren Sie, wann Sie das Schreiben tatsächlich erhalten haben, und handeln Sie vorsichtshalber bis zu diesem Datum.")
    elif relative and not deadline:
        steps.insert(0, f"Im Schreiben steht eine Frist ({relative[0].raw}). Notieren Sie das Datum, an dem Sie es erhalten haben.")

    return CivicAnswer(
        what_is_this=(
            f"{analysis.document_type.replace('_', ' ')} · {analysis.authority_hint}"
            if analysis and analysis.authority_hint
            else ("Behördliches/administratives Dokument" if analysis else None)
        ),
        what_does_it_mean=meaning,
        what_should_i_do=steps,
        deadline=deadline,
        relative_deadlines=relative,
        documents_needed=analysis.requested_items if analysis else [],
        requirements=requirements,
        appeal_instruction=appeal,
        legal_references=refs,
        evidence=bundle.items,
        sources=bundle.items,
        certainty=certainty,
        warnings=(analysis.warnings if analysis else []) + bundle.warnings + grounded_warning,
    )


# ---------------------------------------------------------------------------
# Chat, appointments, letters and forms
# ---------------------------------------------------------------------------


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Conversation on top of the evidence-bound pipeline. Stateless: the client sends the history."""
    try:
        message = last_user_message(req.messages)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    answer = await build_answer(
        message,
        req.document_id,
        model_question_text=model_question(req.messages),
        search_text=retrieval_query(req.messages),
    )
    stored = _stored_document(req.document_id)
    actions = detect_actions(message, stored[1] if stored else None, answer)
    return ChatResponse(reply=compose_reply(answer), answer=answer, actions=actions)


@app.post("/v1/appointments/prepare", response_model=AppointmentPlan)
def appointments_prepare(req: AppointmentRequest):
    """Find the responsible office, the official booking route and a checklist. Never books."""
    return prepare_appointment(req.concern, req.postal_code)


@app.post("/v1/letters/draft", response_model=LetterDraft)
def letters_draft(req: LetterRequest):
    """Draft a reply letter from reviewed templates. The person checks, signs and sends it."""
    stored = _stored_document(req.document_id)
    text, analysis = stored if stored else (None, None)
    return draft_letter(req, analysis=analysis, document_text=text)


@app.post("/v1/forms", response_model=FormInfo)
async def forms_upload(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Leere Datei.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei ist zu groß.")
    form_id = "form_" + uuid.uuid4().hex[:16]
    try:
        info = await run_in_threadpool(read_form, data, form_id, file.filename or "formular.pdf")
    except FormError as exc:
        raise HTTPException(415, str(exc)) from exc
    FORMS.put(form_id, data, info)
    return info


def _stored_form(form_id: str):
    stored = FORMS.get(form_id)
    if not stored:
        raise HTTPException(404, "Formular nicht gefunden oder bereits gelöscht.")
    return stored


@app.post("/v1/forms/{form_id}/suggest", response_model=FormSuggestions)
async def forms_suggest(form_id: str, req: FormSuggestRequest):
    """Suggest values from the person's own entries and the uploaded letter. Nothing is invented."""
    from .forms import clean_profile

    _, info = _stored_form(form_id)
    stored = _stored_document(req.document_id)
    ctx = SuggestContext(profile=clean_profile(req.profile), reference=extract_reference(stored[0]) if stored else None)
    suggestions, unmatched = suggest_by_label(info.fields, ctx)
    notes: list[str] = []
    if req.use_model_for_mapping and unmatched:
        try:
            suggestions += await suggest_by_model(model_provider, unmatched, ctx)
        except ModelProviderError as exc:
            notes.append(f"Zuordnung per Sprachmodell nicht verfügbar: {exc}")
    filled = {s.field_id for s in suggestions}
    unfilled = [f.label for f in info.fields if f.type in {"text", "choice"} and f.id not in filled and not f.value]
    if any(f.type in {"checkbox", "radio"} for f in info.fields):
        notes.append("Ankreuzfelder und Auswahlknöpfe sind Ihre Entscheidung und werden nie automatisch gesetzt.")
    if any(f.type == "signature" for f in info.fields):
        notes.append("Unterschreiben Sie nach dem Ausdrucken bzw. mit Ihrer eigenen Signatur.")
    return FormSuggestions(form_id=form_id, suggestions=suggestions, unfilled=unfilled, notes=notes)


@app.post("/v1/forms/{form_id}/fill")
async def forms_fill(form_id: str, req: FormFillRequest):
    """Return the filled PDF for download. It is not submitted anywhere."""
    data, info = _stored_form(form_id)
    try:
        pdf = await run_in_threadpool(fill_form, data, info, req.values)
    except FormError as exc:
        raise HTTPException(422, str(exc)) from exc
    name = (info.filename.rsplit(".", 1)[0] or "formular") + "-ausgefuellt.pdf"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}"'})


@app.delete("/v1/forms/{form_id}", status_code=204)
def forms_delete(form_id: str):
    if not FORMS.delete(form_id):
        raise HTTPException(404, "Formular nicht gefunden.")
    return Response(status_code=204)
