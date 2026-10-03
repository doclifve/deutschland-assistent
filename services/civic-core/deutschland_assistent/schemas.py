from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
RequirementKind = Literal["document", "information", "payment", "action", "unknown"]


class LegalReference(BaseModel):
    raw: str
    section: str
    law: str
    source_url: str | None = None


class Deadline(BaseModel):
    date: date
    label: str = "Mögliche Frist"
    confidence: Confidence = "medium"
    evidence_text: str | None = None


class RelativeDeadline(BaseModel):
    """A period stated relative to an event, e.g. 'innerhalb eines Monats nach Bekanntgabe'."""

    raw: str
    period_value: int
    period_unit: Literal["days", "weeks", "months"]
    trigger: str
    document_date: date | None = None
    assumed_trigger_date: date | None = None
    estimated_end: date | None = None
    basis: list[str] = Field(default_factory=list)
    confidence: Confidence = "low"


class Requirement(BaseModel):
    text: str
    kind: RequirementKind = "unknown"
    due_date: date | None = None
    confidence: Confidence = "medium"
    evidence_text: str | None = None


class AppealInstruction(BaseModel):
    remedy: Literal["widerspruch", "einspruch", "klage", "beschwerde", "unknown"]
    deadline_expression: str | None = None
    explicit_deadline: date | None = None
    recipient: str | None = None
    methods: list[str] = Field(default_factory=list)
    evidence_text: str
    confidence: Confidence = "medium"


class DocumentAnalysis(BaseModel):
    document_id: str
    filename: str
    document_type: str
    parsing_engine: str = "basic"
    text_preview: str
    document_date: date | None = None
    deadlines: list[Deadline] = Field(default_factory=list)
    relative_deadlines: list[RelativeDeadline] = Field(default_factory=list)
    legal_references: list[LegalReference] = Field(default_factory=list)
    leika_ids: list[str] = Field(default_factory=list)
    authority_hint: str | None = None
    requested_items: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    appeal_instruction: AppealInstruction | None = None
    warnings: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    id: str
    source_id: str
    kind: Literal[
        "user_document",
        "official_law",
        "official_legal_api",
        "official_service",
        "official_guidance",
        "official_case_law",
    ]
    authority: str
    title: str
    url: str | None = None
    locator: str | None = None
    snippet: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    exact_match: bool = False
    jurisdiction: str = "DE"
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    effective_on: date | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    query: str
    items: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    language: str = "de"
    document_id: str | None = None


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=8, ge=1, le=30)
    include_case_law: bool = True


class CivicAnswer(BaseModel):
    what_is_this: str | None = None
    what_does_it_mean: str
    what_should_i_do: list[str] = Field(default_factory=list)
    deadline: Deadline | None = None
    relative_deadlines: list[RelativeDeadline] = Field(default_factory=list)
    documents_needed: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    appeal_instruction: AppealInstruction | None = None
    missing_information: list[str] = Field(default_factory=list)
    legal_references: list[LegalReference] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    sources: list[EvidenceItem] = Field(default_factory=list)
    certainty: Confidence = "medium"
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Informationshilfe, keine individuelle Rechtsberatung oder Behördenentscheidung. "
        "Maßgeblich sind Originaldokumente und amtliche Quellen."
    )


class WhatsAppChannel(BaseModel):
    """Public connection details for the WhatsApp channel. Contains nothing secret."""

    enabled: bool = False
    display_number: str | None = None
    link: str | None = None
    greeting: str = "Hallo"


class ChannelsInfo(BaseModel):
    whatsapp: WhatsAppChannel = Field(default_factory=WhatsAppChannel)


# ---------------------------------------------------------------------------
# Chat, appointments, letters and forms
# ---------------------------------------------------------------------------

ActionKind = Literal["letter", "appointment", "form"]
LetterKind = Literal["widerspruch", "fristverlaengerung", "nachreichung"]


class Link(BaseModel):
    label: str
    url: str
    kind: Literal["official_service", "official_search", "official_law", "online_service"] = "official_service"


class SuggestedAction(BaseModel):
    """Something the assistant can prepare next. Never executed without the person."""

    kind: ActionKind
    label: str
    params: dict[str, str] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    document_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    answer: CivicAnswer
    actions: list[SuggestedAction] = Field(default_factory=list)


class AppointmentRequest(BaseModel):
    concern: str = Field(min_length=1, max_length=300)
    postal_code: str | None = Field(default=None, max_length=10)


class AppointmentPlan(BaseModel):
    concern_id: str | None = None
    title: str
    office: str
    steps: list[str] = Field(default_factory=list)
    bring: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, str]] = Field(default_factory=list)
    disclaimer: str = (
        "Die Buchung nehmen Sie selbst vor. Die zuständige Stelle nennt die verbindliche Liste der Unterlagen."
    )


class LetterRequest(BaseModel):
    kind: LetterKind
    document_id: str | None = None
    sender_name: str | None = Field(default=None, max_length=200)
    sender_address: str | None = Field(default=None, max_length=400)
    recipient: str | None = Field(default=None, max_length=400)
    reference: str | None = Field(default=None, max_length=120)
    decision_date: date | None = None
    letter_date: date | None = None
    place: str | None = Field(default=None, max_length=80)
    reason: str | None = Field(default=None, max_length=4000)
    requested_until: date | None = None
    items: list[str] = Field(default_factory=list, max_length=20)


class LetterDraft(BaseModel):
    kind: LetterKind
    title: str
    sender_block: str
    recipient_block: str
    place_date: str
    subject: str
    body: str
    full_text: str
    missing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    legal: list[Link] = Field(default_factory=list)


FormFieldType = Literal["text", "checkbox", "radio", "choice", "signature", "unknown"]

PROFILE_KEYS = (
    "vorname", "nachname", "geburtsname", "geburtsdatum", "geburtsort", "staatsangehoerigkeit",
    "strasse", "hausnummer", "plz", "ort", "telefon", "email", "aktenzeichen", "datum",
)


class FormOption(BaseModel):
    value: str
    text: str


class FormField(BaseModel):
    id: str
    type: FormFieldType
    label: str
    page: int | None = None
    value: str | None = None
    options: list[FormOption] = Field(default_factory=list)
    checked_value: str | None = None
    required: bool = False
    max_length: int | None = None


class FormInfo(BaseModel):
    form_id: str
    filename: str
    pages: int
    fields: list[FormField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FormSuggestRequest(BaseModel):
    """Values come from the person (profile) or the uploaded letter. Nothing is invented."""

    profile: dict[str, str] = Field(default_factory=dict)
    document_id: str | None = None
    use_model_for_mapping: bool = True


class FieldSuggestion(BaseModel):
    field_id: str
    value: str
    source: Literal["Ihre Angaben", "Schreiben", "Heute"]
    matched_by: Literal["label", "model"] = "label"


class FormSuggestions(BaseModel):
    form_id: str
    suggestions: list[FieldSuggestion] = Field(default_factory=list)
    unfilled: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FormFillRequest(BaseModel):
    values: dict[str, str | bool] = Field(default_factory=dict)
