from __future__ import annotations

import os
import threading
import time
import uuid

from fastapi import FastAPI, File, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .appointments import prepare_appointment
from .channels import channels_info
from .actions import ActionStore, fill_pdf_form, inspect_pdf_form, new_action
from .agent_planning import map_profile_to_form
from .chat import chat as chat_with_assistant
from .documents import DocumentParseError, parse_document
from .forms import FormError, FormStore, SuggestContext, fill_form, read_form, suggest_by_label, suggest_by_model
from .letters import draft_letter, extract_reference
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
    ActionCompleteRequest,
    AppointmentPlan,
    AppointmentRequest,
    ActionConfirmRequest,
    ActionPreview,
    AppointmentPrepareRequest,
    AskRequest,
    ChatRequest,
    ChatResponse,
    FormFillRequest,
    FormInfo,
    FormSuggestions,
    FormSuggestRequest,
    LetterDraft,
    LetterRequest,
    FormAgentPrepareRequest,
    FormFillPrepareRequest,
    FormInspection,
    ChannelsInfo,
    CivicAnswer,
    Deadline,
    DocumentAnalysis,
    EvidenceBundle,
    EvidenceSearchRequest,
    RelativeDeadline,
)

VERSION = "0.3.0"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_DOCUMENT_PAGES = int(os.getenv("MAX_DOCUMENT_PAGES", "30"))
DOCUMENT_ENGINE = os.getenv("DOCUMENT_ENGINE", "auto")
DOCUMENT_TTL_SECONDS = int(os.getenv("DOCUMENT_TTL_SECONDS", "3600"))
MAX_STORED_DOCUMENTS = int(os.getenv("MAX_STORED_DOCUMENTS", "500"))
ACTION_TTL_SECONDS = int(os.getenv("ACTION_TTL_SECONDS", "3600"))
MAX_AGENT_FORM_BYTES = int(os.getenv("MAX_AGENT_FORM_BYTES", str(10 * 1024 * 1024)))
AGENT_EXECUTION_TOKEN = os.getenv("AGENT_EXECUTION_TOKEN", "").strip()
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
engine = EvidenceEngine()
model_provider = build_model_provider()
ACTION_STORE = ActionStore(ttl_seconds=ACTION_TTL_SECONDS)
FORMS = FormStore(DOCUMENT_TTL_SECONDS, MAX_STORED_DOCUMENTS)


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



def _analysis_for_document(document_id: str | None) -> DocumentAnalysis | None:
    if not document_id:
        return None
    stored = STORE.get(document_id)
    if not stored:
        raise HTTPException(404, "Dokument nicht gefunden oder bereits gelöscht.")
    return stored[1]


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    analysis = _analysis_for_document(req.document_id)
    return await chat_with_assistant(
        model_provider,
        engine,
        messages=req.messages,
        language=req.language,
        analysis=analysis,
    )



@app.post("/v1/appointments/prepare", response_model=AppointmentPlan)
def appointments_prepare(req: AppointmentRequest):
    """Find official routes, likely documents and next steps. This endpoint never books."""
    return prepare_appointment(req.concern, req.postal_code)


@app.post("/v1/letters/draft", response_model=LetterDraft)
def letters_draft(req: LetterRequest):
    """Create a deterministic draft. The person reviews, signs and sends it."""
    analysis = None
    text = None
    if req.document_id:
        stored = STORE.get(req.document_id)
        if not stored:
            raise HTTPException(404, "Dokument nicht gefunden oder bereits gelöscht.")
        text, analysis = stored
    return draft_letter(req, analysis=analysis, document_text=text)


@app.post("/v1/forms", response_model=FormInfo)
async def forms_upload(file: UploadFile = File(...)):
    data = await file.read(MAX_AGENT_FORM_BYTES + 1)
    if not data:
        raise HTTPException(400, "Leere Datei.")
    if len(data) > MAX_AGENT_FORM_BYTES:
        raise HTTPException(413, "Formular ist zu groß.")
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
    """Suggest field values only from user data / document facts; never invent personal data."""
    from .forms import clean_profile

    _, info = _stored_form(form_id)
    stored = STORE.get(req.document_id) if req.document_id else None
    if req.document_id and not stored:
        raise HTTPException(404, "Dokument nicht gefunden oder bereits gelöscht.")
    ctx = SuggestContext(
        profile=clean_profile(req.profile),
        reference=extract_reference(stored[0]) if stored else None,
    )
    suggestions, unmatched = suggest_by_label(info.fields, ctx)
    notes: list[str] = []
    if req.use_model_for_mapping and unmatched:
        try:
            suggestions += await suggest_by_model(model_provider, unmatched, ctx)
        except ModelProviderError as exc:
            notes.append(f"Zuordnung per Sprachmodell nicht verfügbar: {exc}")
    filled = {s.field_id for s in suggestions}
    unfilled = [
        f.label
        for f in info.fields
        if f.type in {"text", "choice"} and f.id not in filled and not f.value
    ]
    if any(f.type in {"checkbox", "radio"} for f in info.fields):
        notes.append("Ankreuzfelder und Auswahlknöpfe sind Ihre Entscheidung und werden nie automatisch gesetzt.")
    if any(f.type == "signature" for f in info.fields):
        notes.append("Unterschriften werden nicht automatisch erzeugt.")
    return FormSuggestions(
        form_id=form_id,
        suggestions=suggestions,
        unfilled=unfilled,
        notes=notes,
    )


@app.post("/v1/forms/{form_id}/fill")
async def forms_fill_legacy(form_id: str, req: FormFillRequest):
    """Fill an interactive PDF and return it. This never submits the form."""
    data, info = _stored_form(form_id)
    try:
        pdf = await run_in_threadpool(fill_form, data, info, req.values)
    except FormError as exc:
        raise HTTPException(422, str(exc)) from exc
    name = (info.filename.rsplit(".", 1)[0] or "formular") + "-ausgefuellt.pdf"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@app.delete("/v1/forms/{form_id}", status_code=204)
def forms_delete(form_id: str):
    if not FORMS.delete(form_id):
        raise HTTPException(404, "Formular nicht gefunden.")
    return Response(status_code=204)


@app.post("/v1/actions/appointment", response_model=ActionPreview)
def prepare_appointment(req: AppointmentPrepareRequest):
    payload = req.model_dump(mode="json", exclude_none=True)
    target = "openclaw_browser" if req.official_booking_url else "connector_required"
    preview = new_action(
        "appointment",
        summary=f"Termin vorbereiten: {req.service}",
        payload=payload,
        execution_target=target,
        ttl_seconds=ACTION_TTL_SECONDS,
    )
    ACTION_STORE.put_action(preview)
    return preview


@app.post("/v1/forms/inspect", response_model=FormInspection)
async def inspect_form(file: UploadFile = File(...)):
    data = await file.read(MAX_AGENT_FORM_BYTES + 1)
    if not data:
        raise HTTPException(400, "Leere Datei.")
    if len(data) > MAX_AGENT_FORM_BYTES:
        raise HTTPException(413, "Formular ist zu groß.")
    filename = file.filename or "formular.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(415, "Der Formular-Agent unterstützt derzeit ausfüllbare PDF-Formulare.")
    try:
        inspection = inspect_pdf_form(data, filename, ACTION_TTL_SECONDS, ACTION_STORE)
    except Exception as exc:
        raise HTTPException(422, f"PDF-Formular konnte nicht gelesen werden: {type(exc).__name__}") from exc
    if not inspection.fields:
        raise HTTPException(422, "In diesem PDF wurden keine ausfüllbaren Formularfelder gefunden.")
    return inspection


@app.post("/v1/forms/{form_id}/prepare", response_model=ActionPreview)
def prepare_form_fill(form_id: str, req: FormFillPrepareRequest):
    form = ACTION_STORE.get_form(form_id)
    if not form:
        raise HTTPException(404, "Formular nicht gefunden oder abgelaufen.")
    allowed = {field.name for field in form.fields}
    values = {k: v for k, v in req.values.items() if k in allowed}
    unknown = sorted(set(req.values) - allowed)
    if unknown:
        raise HTTPException(422, f"Unbekannte Formularfelder: {', '.join(unknown[:8])}")
    preview = new_action(
        "form_fill",
        summary=f"Formular ausfüllen: {form.filename}",
        payload={"form_id": form_id, "filename": form.filename, "values": values},
        execution_target="civic_core_pdf",
        ttl_seconds=ACTION_TTL_SECONDS,
    )
    ACTION_STORE.put_action(preview)
    return preview


@app.post("/v1/forms/{form_id}/agent-prepare", response_model=ActionPreview)
async def agent_prepare_form(form_id: str, req: FormAgentPrepareRequest):
    form = ACTION_STORE.get_form(form_id)
    if not form:
        raise HTTPException(404, "Formular nicht gefunden oder abgelaufen.")
    try:
        mapping = await map_profile_to_form(
            model_provider,
            fields=form.fields,
            profile=req.profile,
            notes=req.notes,
        )
    except ModelProviderError as exc:
        raise HTTPException(503, str(exc)) from exc
    preview = new_action(
        "form_fill",
        summary=f"Formular-Agent: {form.filename}",
        payload={
            "form_id": form_id,
            "filename": form.filename,
            "values": mapping.values,
            "unresolved": mapping.unresolved,
        },
        execution_target="civic_core_pdf",
        ttl_seconds=ACTION_TTL_SECONDS,
    )
    ACTION_STORE.put_action(preview)
    return preview


@app.get("/v1/actions/{action_id}", response_model=ActionPreview)
def get_action(action_id: str):
    stored = ACTION_STORE.get_action(action_id)
    if not stored:
        raise HTTPException(404, "Aktion nicht gefunden oder abgelaufen.")
    return stored.preview


@app.post("/v1/actions/{action_id}/confirm", response_model=ActionPreview)
def confirm_action(action_id: str, req: ActionConfirmRequest):
    stored = ACTION_STORE.get_action(action_id)
    if not stored:
        raise HTTPException(404, "Aktion nicht gefunden oder abgelaufen.")
    current = stored.preview
    if current.version != req.expected_version:
        raise HTTPException(409, "Die Aktionsvorschau wurde zwischenzeitlich geändert.")
    if current.status != "prepared":
        raise HTTPException(409, f"Aktion ist bereits im Status {current.status}.")

    if not req.approve:
        updated = current.model_copy(
            update={"status": "cancelled", "version": current.version + 1}
        )
        ACTION_STORE.update_action(action_id, updated)
        return updated

    artifact = None
    artifact_name = None
    artifact_url = None
    new_status = "approved"

    if current.action_type == "form_fill":
        form_id = str(current.payload.get("form_id") or "")
        form = ACTION_STORE.get_form(form_id)
        if not form:
            raise HTTPException(404, "Das zugehörige Formular ist abgelaufen.")
        values = current.payload.get("values") or {}
        try:
            artifact = fill_pdf_form(form.data, {str(k): str(v) for k, v in values.items()})
        except Exception as exc:
            raise HTTPException(422, f"Formular konnte nicht ausgefüllt werden: {type(exc).__name__}") from exc
        artifact_name = "ausgefuellt-" + form.filename
        artifact_url = f"/v1/actions/{action_id}/artifact"
        new_status = "completed"

    updated = current.model_copy(
        update={
            "status": new_status,
            "version": current.version + 1,
            "artifact_url": artifact_url,
        }
    )
    ACTION_STORE.update_action(action_id, updated, artifact=artifact, artifact_name=artifact_name)
    return updated


@app.get("/v1/actions/{action_id}/artifact")
def action_artifact(action_id: str):
    stored = ACTION_STORE.get_action(action_id)
    if not stored or not stored.artifact:
        raise HTTPException(404, "Kein Artefakt für diese Aktion vorhanden.")
    filename = stored.artifact_name or "dokument.pdf"
    return Response(
        content=stored.artifact,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/v1/actions/{action_id}/complete", response_model=ActionPreview)
def complete_external_action(
    action_id: str,
    req: ActionCompleteRequest,
    x_agent_token: str | None = Header(default=None),
):
    if not AGENT_EXECUTION_TOKEN:
        raise HTTPException(503, "Externe Agentenausführung ist nicht konfiguriert.")
    if x_agent_token != AGENT_EXECUTION_TOKEN:
        raise HTTPException(401, "Ungültiger Agent-Token.")
    stored = ACTION_STORE.get_action(action_id)
    if not stored:
        raise HTTPException(404, "Aktion nicht gefunden oder abgelaufen.")
    current = stored.preview
    if current.action_type != "appointment" or current.status != "approved":
        raise HTTPException(409, "Nur bestätigte Terminaktionen können extern abgeschlossen werden.")
    payload = dict(current.payload)
    payload["execution_result"] = req.result_summary
    if req.external_reference:
        payload["external_reference"] = req.external_reference
    if req.appointment_time:
        payload["appointment_time"] = req.appointment_time.isoformat()
    updated = current.model_copy(
        update={
            "status": "completed" if req.success else "failed",
            "version": current.version + 1,
            "payload": payload,
        }
    )
    ACTION_STORE.update_action(action_id, updated)
    return updated


@app.post("/v1/ask", response_model=CivicAnswer)
async def ask(req: AskRequest):
    text = req.message
    analysis = None
    if req.document_id:
        stored = STORE.get(req.document_id)
        if not stored:
            raise HTTPException(404, "Dokument nicht gefunden oder bereits gelöscht.")
        text, analysis = stored

    refs = analysis.legal_references if analysis else extract_legal_references(text)
    deadlines = analysis.deadlines if analysis else extract_deadlines(text)
    relative = analysis.relative_deadlines if analysis else extract_relative_deadlines(text)
    leika = analysis.leika_ids if analysis else extract_leika_ids(text)
    requirements = analysis.requirements if analysis else extract_requirements(text)
    appeal = analysis.appeal_instruction if analysis else extract_appeal_instruction(text)
    deadline = primary_deadline(deadlines, relative)

    query = (
        req.message
        if not analysis
        else " ".join(
            x
            for x in [
                analysis.authority_hint or "",
                " ".join(r.raw for r in refs),
                analysis.document_type.replace("_", " "),
                appeal.remedy if appeal else "",
                req.message,
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
            question=req.message,
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
