from __future__ import annotations

import io
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

VERSION = "0.1.0"
LAW_SLUGS = {
    "BGB":"bgb","GG":"gg","AO":"ao_1977","STGB":"stgb","ZPO":"zpo","VWGO":"vwgo",
    "SGB I":"sgb_1","SGB II":"sgb_2","SGB III":"sgb_3","SGB IV":"sgb_4","SGB V":"sgb_5",
    "SGB VI":"sgb_6","SGB VII":"sgb_7","SGB VIII":"sgb_8","SGB IX":"sgb_9_2018","SGB X":"sgb_10",
    "SGB XI":"sgb_11","SGB XII":"sgb_12"
}
LEGAL_REF = re.compile(r"(?P<section>§{1,2}\s*\d+[a-zA-Z]?(?:\s*(?:Abs\.|Absatz)\s*\d+)?)\s+(?P<law>(?:SGB\s*[IVXLC]+|BGB|GG|AO|VwVfG|StGB|ZPO|VwGO|SGG|EStG))\b", re.I)
DATE_RE = re.compile(r"\b(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\.(?P<y>20\d{2})\b")
DEADLINE_HINT = re.compile(r"\b(frist|bis zum|spätestens|innerhalb|widerspruch|einzureichen|vorzulegen)\b", re.I)

class Evidence(BaseModel):
    title: str
    url: str | None = None
    locator: str | None = None
    kind: str = "official_source"

class Deadline(BaseModel):
    date: date
    label: str = "Mögliche Frist"
    confidence: Literal["high","medium","low"] = "medium"

class LegalReference(BaseModel):
    raw: str
    section: str
    law: str
    source_url: str | None = None

class DocumentAnalysis(BaseModel):
    document_id: str
    filename: str
    document_type: str
    text_preview: str
    deadlines: list[Deadline] = []
    legal_references: list[LegalReference] = []
    warnings: list[str] = []

class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    language: str = "de"
    document_id: str | None = None

class CivicAnswer(BaseModel):
    what_is_this: str | None = None
    what_does_it_mean: str
    what_should_i_do: list[str] = []
    deadline: Deadline | None = None
    legal_references: list[LegalReference] = []
    sources: list[Evidence] = []
    certainty: Literal["high","medium","low"] = "medium"
    disclaimer: str = "Informationshilfe, keine individuelle Rechtsberatung oder Behördenentscheidung."

STORE: dict[str, tuple[str, DocumentAnalysis]] = {}

def law_url(law: str, section: str) -> str:
    key = re.sub(r"\s+"," ",law.upper()).strip()
    slug = LAW_SLUGS.get(key)
    if not slug:
        return "https://www.gesetze-im-internet.de/"
    m = re.search(r"\d+[a-zA-Z]?", section)
    return f"https://www.gesetze-im-internet.de/{slug}/__{m.group(0).lower()}.html" if m else f"https://www.gesetze-im-internet.de/{slug}/"

def extract_refs(text: str) -> list[LegalReference]:
    out=[]
    for m in LEGAL_REF.finditer(text):
        section=re.sub(r"\s+"," ",m.group("section")).strip()
        law=re.sub(r"\s+"," ",m.group("law").upper()).strip()
        out.append(LegalReference(raw=m.group(0), section=section, law=law, source_url=law_url(law, section)))
    return out

def extract_deadlines(text: str) -> list[Deadline]:
    out=[]
    for m in DATE_RE.finditer(text):
        context=text[max(0,m.start()-90):min(len(text),m.end()+90)]
        if not DEADLINE_HINT.search(context):
            continue
        try:
            out.append(Deadline(date=date(int(m.group("y")),int(m.group("m")),int(m.group("d"))), confidence="high"))
        except ValueError:
            pass
    return out

def read_document(data: bytes, filename: str) -> str:
    suffix=Path(filename).suffix.lower()
    if suffix in {".txt",".md",".csv"}:
        return data.decode("utf-8", errors="replace")
    if suffix==".pdf":
        reader=PdfReader(io.BytesIO(data))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    raise HTTPException(status_code=415, detail="v0.1 unterstützt direkt PDF/Text. Fotos/Scans werden über die optionale Docling/OCR-Schicht ergänzt.")

def classify(text: str) -> str:
    t=text.lower()
    if any(x in t for x in ["bescheid","rechtsbehelfsbelehrung","widerspruchsbelehrung"]): return "authority_decision"
    if "rechnung" in t: return "invoice"
    if any(x in t for x in ["vertrag","kündigung"]): return "contract_or_notice"
    return "unknown"

app=FastAPI(title="Deutschland Assistent API",version=VERSION,description="Evidence-first civic assistance core for Germany.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"])

@app.get("/health")
def health():
    return {"status":"ok","service":"deutschland-assistent-core","version":VERSION}

@app.post("/v1/documents",response_model=DocumentAnalysis)
async def documents(file: UploadFile=File(...)):
    data=await file.read(15*1024*1024+1)
    if not data: raise HTTPException(400,"Leere Datei.")
    if len(data)>15*1024*1024: raise HTTPException(413,"Datei ist zu groß.")
    text=read_document(data,file.filename or "document")
    doc_id="doc_"+uuid.uuid4().hex[:16]
    analysis=DocumentAnalysis(
        document_id=doc_id, filename=file.filename or "document", document_type=classify(text),
        text_preview=" ".join(text.split())[:2500], deadlines=extract_deadlines(text),
        legal_references=extract_refs(text),
        warnings=[] if text.strip() else ["Kein Text erkannt; OCR/Docling aktivieren."]
    )
    STORE[doc_id]=(text,analysis)
    return analysis

@app.post("/v1/ask",response_model=CivicAnswer)
def ask(req: AskRequest):
    text=req.message
    analysis=None
    if req.document_id:
        stored=STORE.get(req.document_id)
        if not stored: raise HTTPException(404,"Dokument nicht gefunden.")
        text=stored[0]
        analysis=stored[1]
    refs=analysis.legal_references if analysis else extract_refs(text)
    deadlines=analysis.deadlines if analysis else extract_deadlines(text)
    sources=[Evidence(title=r.raw,url=r.source_url,locator=r.section,kind="official_law") for r in refs]
    if analysis:
        meaning="Das Dokument wurde strukturiert gelesen. Explizite Fristen und Gesetzeszitate werden unten getrennt ausgewiesen."
        steps=["Prüfen Sie die erkannte Frist und die verlangten Unterlagen im Originaldokument.","Öffnen Sie die offiziellen Quellen zu erkannten Gesetzeszitaten."]
    elif refs:
        meaning="Ich habe eine konkrete deutsche Rechtsnorm erkannt und verlinke auf die offizielle Fassung."
        steps=["Lesen Sie die verlinkte Norm im Original.","Für eine Einzelfallbewertung sind zusätzliche Tatsachen erforderlich."]
    else:
        meaning="v0.1 beantwortet allgemeine Fragen noch deterministisch und verweist bei Rechtsfragen auf offizielle Quellen."
        steps=["Formulieren Sie die konkrete Behörde, Leistung oder Rechtsnorm.","Laden Sie bei einem Schreiben das Dokument hoch."]
    return CivicAnswer(
        what_is_this=("Behördliches/administratives Dokument" if analysis else None),
        what_does_it_mean=meaning, what_should_i_do=steps,
        deadline=deadlines[0] if deadlines else None, legal_references=refs, sources=sources,
        certainty="high" if (refs or deadlines) else "medium"
    )
