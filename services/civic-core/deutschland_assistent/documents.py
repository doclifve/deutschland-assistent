from __future__ import annotations
import io,os,tempfile
from dataclasses import dataclass,field
from pathlib import Path
from pypdf import PdfReader

IMAGE_SUFFIXES={".png",".jpg",".jpeg",".webp",".tif",".tiff",".bmp"}
TEXT_SUFFIXES={".txt",".md",".csv",".json",".xml",".html",".htm"}

@dataclass
class ParsedDocument:
    text:str
    engine:str
    warnings:list[str]=field(default_factory=list)

class DocumentParseError(RuntimeError):pass

def _basic(data:bytes,filename:str)->ParsedDocument:
    suffix=Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIXES:return ParsedDocument(data.decode("utf-8",errors="replace"),"basic-text")
    if suffix==".pdf":
        try:
            reader=PdfReader(io.BytesIO(data));text="\n\n".join((p.extract_text() or "") for p in reader.pages);warnings=[]
            if len(text.strip())<80:warnings.append("PDF enthält wenig extrahierbaren Text; OCR kann erforderlich sein.")
            return ParsedDocument(text,"pypdf",warnings)
        except Exception as exc:raise DocumentParseError(f"PDF konnte nicht gelesen werden: {exc}") from exc
    if suffix in IMAGE_SUFFIXES:return ParsedDocument("","basic",["Bild benötigt OCR/Docling."])
    raise DocumentParseError(f"Dateityp {suffix or '(ohne Endung)'} wird nicht unterstützt.")

def _docling(data:bytes,filename:str)->ParsedDocument:
    try:from docling.document_converter import DocumentConverter
    except ImportError as exc:raise DocumentParseError("Docling ist nicht installiert. Installiere den optionalen Extra 'docling'.") from exc
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".bin",delete=False) as h:h.write(data);tmp=h.name
        result=DocumentConverter().convert(tmp)
        return ParsedDocument(result.document.export_to_markdown(),"docling",[])
    except Exception as exc:raise DocumentParseError(f"Docling konnte das Dokument nicht lesen: {exc}") from exc
    finally:
        if tmp:
            try:os.unlink(tmp)
            except OSError:pass

def parse_document(data:bytes,filename:str,mode:str="auto")->ParsedDocument:
    mode=(mode or "auto").lower();suffix=Path(filename).suffix.lower()
    if mode=="docling":return _docling(data,filename)
    basic=_basic(data,filename)
    if mode=="basic":return basic
    if suffix in IMAGE_SUFFIXES or (suffix==".pdf" and len(basic.text.strip())<80):
        try:
            parsed=_docling(data,filename);parsed.warnings.extend(basic.warnings);return parsed
        except DocumentParseError as exc:basic.warnings.append(str(exc))
    return basic
