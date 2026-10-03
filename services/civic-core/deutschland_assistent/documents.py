from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"}


@dataclass
class ParsedDocument:
    text: str
    engine: str
    warnings: list[str] = field(default_factory=list)


class DocumentParseError(RuntimeError):
    pass


def _basic(data: bytes, filename: str) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return ParsedDocument(data.decode("utf-8", errors="replace"), "basic-text")
    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
            warnings: list[str] = []
            if len(text.strip()) < 120:
                warnings.append("PDF enthält wenig extrahierbaren Text; OCR wird im Auto-Modus versucht.")
            return ParsedDocument(text, "pypdf", warnings)
        except Exception as exc:
            raise DocumentParseError(f"PDF konnte nicht gelesen werden: {exc}") from exc
    if suffix in IMAGE_SUFFIXES:
        return ParsedDocument("", "basic", ["Bild benötigt OCR/Docling."])
    raise DocumentParseError(f"Dateityp {suffix or '(ohne Endung)'} wird nicht unterstützt.")


def _docling(
    data: bytes,
    filename: str,
    *,
    full_page_ocr: bool,
    max_pages: int,
    max_file_size: int,
) -> ParsedDocument:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import OcrAutoOptions, OcrMode, PdfPipelineOptions
        from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
    except ImportError as exc:
        raise DocumentParseError(
            "Docling ist nicht installiert. Installiere den optionalen Extra 'docling'."
        ) from exc

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.enable_remote_services = False
    pipeline_options.ocr_options = OcrAutoOptions(
        lang=["iso:de", "iso:en"],
        mode=OcrMode.FULL_PAGE if full_page_ocr else OcrMode.DEFAULT,
    )
    artifacts_path = os.getenv("DOCLING_ARTIFACTS_PATH")
    if artifacts_path:
        pipeline_options.artifacts_path = Path(artifacts_path)

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
        }
    )
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".bin", delete=False) as h:
            h.write(data)
            tmp = h.name
        result = converter.convert(
            tmp,
            max_num_pages=max_pages,
            max_file_size=max_file_size,
        )
        text = result.document.export_to_markdown()
        warnings = [] if text.strip() else ["Docling/OCR hat keinen verwertbaren Text erzeugt."]
        return ParsedDocument(text, "docling-ocr" if full_page_ocr else "docling", warnings)
    except Exception as exc:
        raise DocumentParseError(f"Docling konnte das Dokument nicht lesen: {exc}") from exc
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def parse_document(
    data: bytes,
    filename: str,
    mode: str = "auto",
    *,
    max_pages: int = 30,
    max_file_size: int = 15 * 1024 * 1024,
) -> ParsedDocument:
    mode = (mode or "auto").lower()
    suffix = Path(filename).suffix.lower()
    if mode not in {"auto", "basic", "docling"}:
        raise DocumentParseError("DOCUMENT_ENGINE muss auto, basic oder docling sein.")
    if mode == "docling":
        return _docling(
            data,
            filename,
            full_page_ocr=suffix in IMAGE_SUFFIXES,
            max_pages=max_pages,
            max_file_size=max_file_size,
        )

    basic = _basic(data, filename)
    if mode == "basic":
        return basic

    needs_ocr = suffix in IMAGE_SUFFIXES or (suffix == ".pdf" and len(basic.text.strip()) < 120)
    if needs_ocr:
        try:
            parsed = _docling(
                data,
                filename,
                full_page_ocr=True,
                max_pages=max_pages,
                max_file_size=max_file_size,
            )
            parsed.warnings.extend(basic.warnings)
            return parsed
        except DocumentParseError as exc:
            basic.warnings.append(str(exc))
    return basic
