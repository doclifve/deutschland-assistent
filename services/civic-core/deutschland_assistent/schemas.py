from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

Confidence = Literal["high","medium","low"]

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
    """A period stated relative to an event, e.g. "innerhalb eines Monats nach Bekanntgabe"."""
    raw: str
    period_value: int
    period_unit: Literal["days","weeks","months"]
    trigger: str
    document_date: date | None = None
    assumed_trigger_date: date | None = None
    estimated_end: date | None = None
    basis: list[str] = Field(default_factory=list)
    confidence: Confidence = "low"

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
    warnings: list[str] = Field(default_factory=list)

class EvidenceItem(BaseModel):
    id: str
    source_id: str
    kind: Literal["user_document","official_law","official_legal_api","official_service","official_guidance","official_case_law"]
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
    message: str = Field(min_length=1,max_length=12000)
    language: str = "de"
    document_id: str | None = None

class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=1,max_length=4000)
    limit: int = Field(default=8,ge=1,le=30)

class CivicAnswer(BaseModel):
    what_is_this: str | None = None
    what_does_it_mean: str
    what_should_i_do: list[str] = Field(default_factory=list)
    deadline: Deadline | None = None
    relative_deadlines: list[RelativeDeadline] = Field(default_factory=list)
    documents_needed: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    legal_references: list[LegalReference] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    sources: list[EvidenceItem] = Field(default_factory=list)
    certainty: Confidence = "medium"
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = "Informationshilfe, keine individuelle Rechtsberatung oder Behördenentscheidung. Maßgeblich sind Originaldokumente und amtliche Quellen."
