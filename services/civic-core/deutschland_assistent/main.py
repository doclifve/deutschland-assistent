from __future__ import annotations
import os,uuid
from fastapi import FastAPI,File,HTTPException,UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .documents import DocumentParseError,parse_document
from .evidence import EvidenceEngine
from .extraction import classify_document,extract_authority_hint,extract_deadlines,extract_leika_ids,extract_legal_references,extract_requested_items
from .schemas import AskRequest,CivicAnswer,DocumentAnalysis,EvidenceBundle,EvidenceSearchRequest

VERSION="0.2.0";MAX_UPLOAD_BYTES=int(os.getenv("MAX_UPLOAD_BYTES",str(15*1024*1024)));DOCUMENT_ENGINE=os.getenv("DOCUMENT_ENGINE","auto")
STORE:dict[str,tuple[str,DocumentAnalysis]]={}
engine=EvidenceEngine()
app=FastAPI(title="Deutschland Assistent API",version=VERSION,description="Evidence-first civic assistance core for Germany.")
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","*").split(","),allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["*"])

@app.get("/health")
def health():return {"status":"ok","service":"deutschland-assistent-core","version":VERSION}

@app.get("/v1/sources")
def sources():
    return {"sources":[
      {"id":"gesetze-im-internet","authority":"BMJ/BfJ","role":"exact legal-reference fallback","status":"authoritative"},
      {"id":"neuris","authority":"BMJ/BfJ / DigitalService","role":"federal legislation search","status":"official-testphase-incomplete"},
      {"id":"bundesportal","authority":"Bundesportal and federal agencies","role":"public-service and benefit guidance","status":"authoritative-curated"},
      {"id":"docling","authority":"document engine","role":"OCR/layout parsing when installed","status":"optional"}]}

@app.post("/v1/documents",response_model=DocumentAnalysis)
async def documents(file:UploadFile=File(...)):
    data=await file.read(MAX_UPLOAD_BYTES+1)
    if not data:raise HTTPException(400,"Leere Datei.")
    if len(data)>MAX_UPLOAD_BYTES:raise HTTPException(413,"Datei ist zu groß.")
    filename=file.filename or "document"
    try:parsed=parse_document(data,filename,mode=DOCUMENT_ENGINE)
    except DocumentParseError as exc:raise HTTPException(415,str(exc)) from exc
    text=parsed.text;doc_id="doc_"+uuid.uuid4().hex[:16]
    analysis=DocumentAnalysis(document_id=doc_id,filename=filename,document_type=classify_document(text),parsing_engine=parsed.engine,text_preview=" ".join(text.split())[:3500],deadlines=extract_deadlines(text),legal_references=extract_legal_references(text),leika_ids=extract_leika_ids(text),authority_hint=extract_authority_hint(text),requested_items=extract_requested_items(text),warnings=parsed.warnings+([] if text.strip() else ["Kein verwertbarer Text erkannt."]))
    STORE[doc_id]=(text,analysis);return analysis

@app.post("/v1/evidence/search",response_model=EvidenceBundle)
async def evidence_search(req:EvidenceSearchRequest):
    return await engine.collect(req.query,extract_legal_references(req.query),extract_leika_ids(req.query),req.limit)

@app.post("/v1/ask",response_model=CivicAnswer)
async def ask(req:AskRequest):
    text=req.message;analysis=None
    if req.document_id:
        stored=STORE.get(req.document_id)
        if not stored:raise HTTPException(404,"Dokument nicht gefunden.")
        text,analysis=stored
    refs=analysis.legal_references if analysis else extract_legal_references(text)
    deadlines=analysis.deadlines if analysis else extract_deadlines(text)
    leika=analysis.leika_ids if analysis else extract_leika_ids(text)
    query=req.message if not analysis else " ".join(x for x in [analysis.authority_hint or ""," ".join(r.raw for r in refs),analysis.document_type.replace("_"," "),req.message] if x)
    bundle=await engine.collect(query[:1800],refs,leika,10)
    if analysis:
        meaning="Das Dokument wurde gelesen und mit amtlichen Quellen abgeglichen. Explizite Fristen und Gesetzeszitate werden getrennt ausgewiesen.";steps=[]
        if deadlines:steps.append("Prüfen Sie die erkannte Frist im Originaldokument.")
        if analysis.requested_items:steps.append("Stellen Sie die im Dokument verlangten Unterlagen zusammen.")
        if refs:steps.append("Vergleichen Sie die genannten Rechtsgrundlagen mit den verlinkten amtlichen Fassungen.")
        if not steps:steps.append("Prüfen Sie Absender, Anliegen und eventuell verlangte nächste Schritte im Original.")
        certainty="high" if deadlines or refs or analysis.requested_items else "medium"
    elif refs:
        meaning="Ich habe ein konkretes Gesetzeszitat erkannt und mit amtlichen Rechtsquellen verknüpft. Für die Anwendung auf einen Einzelfall können weitere Tatsachen erforderlich sein.";steps=["Öffnen Sie die amtliche Fassung der Norm.","Beschreiben Sie den konkreten Sachverhalt, wenn Sie die Bedeutung für Ihren Fall einordnen möchten."];certainty="high"
    else:
        meaning="Ich habe amtliche Quellen zu Ihrer Frage gesucht. Die Treffer dienen als nachvollziehbare Grundlage; eine individuelle Rechtsfolge wird daraus nicht automatisch abgeleitet.";steps=["Öffnen Sie die relevantesten amtlichen Quellen.","Laden Sie ein Schreiben hoch, wenn sich die Frage auf einen konkreten Bescheid oder Brief bezieht."];certainty="medium" if bundle.items else "low"
    return CivicAnswer(what_is_this=(f"{analysis.document_type.replace('_',' ')} · {analysis.authority_hint}" if analysis and analysis.authority_hint else ("Behördliches/administratives Dokument" if analysis else None)),what_does_it_mean=meaning,what_should_i_do=steps,deadline=deadlines[0] if deadlines else None,documents_needed=analysis.requested_items if analysis else [],legal_references=refs,evidence=bundle.items,sources=bundle.items,certainty=certainty,warnings=(analysis.warnings if analysis else [])+bundle.warnings)
