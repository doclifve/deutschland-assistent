"""Draft reply letters to authorities from fixed, reviewed templates.

Templates are deterministic on purpose: the wording of a Widerspruch or a request
for more time must not depend on a language model. Missing details are left as
visible [placeholders] and listed, never invented. Nothing is sent: the person
reviews, signs and sends the letter.
"""
from __future__ import annotations

import re
from datetime import date

from .schemas import AppealInstruction, DocumentAnalysis, LetterDraft, LetterRequest, Link

REFERENCE_RE = re.compile(
    r"(?:Aktenzeichen|Az\.|Geschäftszeichen|Gesch\.-Z\.|Unser Zeichen|BG-Nummer|Kundennummer|Steuernummer)"
    # First token, then further tokens only if they start with a digit ("BG 12345/67") or are a short
    # register letter followed by a number ("3 K 123/26").
    r"\s*[:.]?\s*(?P<ref>[A-Za-z0-9][A-Za-z0-9./\-]*(?:[ ](?:[0-9][A-Za-z0-9./\-]*|[A-Z]{1,3}(?=[ ][0-9])))*)",
    re.I,
)

LAW_LINKS = {
    "sgg84": Link(label="§ 84 SGG – Widerspruchsfrist und Form", url="https://www.gesetze-im-internet.de/sgg/__84.html", kind="official_law"),
    "vwgo70": Link(label="§ 70 VwGO – Form und Frist des Widerspruchs", url="https://www.gesetze-im-internet.de/vwgo/__70.html", kind="official_law"),
    "ao357": Link(label="§ 357 AO – Einlegung des Einspruchs", url="https://www.gesetze-im-internet.de/ao_1977/__357.html", kind="official_law"),
}

TITLES = {
    "widerspruch": "Widerspruch",
    "fristverlaengerung": "Bitte um Fristverlängerung",
    "nachreichung": "Nachreichung von Unterlagen",
}


def extract_reference(text: str) -> str | None:
    for m in REFERENCE_RE.finditer(text[:6000]):
        ref = m.group("ref").strip(" .-/")
        if any(ch.isdigit() for ch in ref) and 3 <= len(ref) <= 40:
            return ref
    return None


def fmt(d: date) -> str:
    return d.strftime("%d.%m.%Y")


class _Filler:
    """Collects visible placeholders for everything the person still has to fill in."""

    def __init__(self) -> None:
        self.missing: list[str] = []

    def __call__(self, value: str | None, placeholder: str) -> str:
        if value and value.strip():
            return value.strip()
        if placeholder not in self.missing:
            self.missing.append(placeholder)
        return f"[{placeholder}]"


def draft_letter(
    req: LetterRequest,
    *,
    analysis: DocumentAnalysis | None = None,
    document_text: str | None = None,
    today: date | None = None,
) -> LetterDraft:
    fill = _Filler()
    today = today or date.today()
    appeal: AppealInstruction | None = analysis.appeal_instruction if analysis else None
    remedy = appeal.remedy if appeal and appeal.remedy in {"widerspruch", "einspruch"} else "widerspruch"

    decision_date = req.decision_date or (analysis.document_date if analysis else None)
    reference = req.reference or (extract_reference(document_text) if document_text else None)
    recipient_default = (appeal.recipient if appeal and appeal.recipient else None) or (analysis.authority_hint if analysis else None)

    sender_block = "\n".join([fill(req.sender_name, "Ihr Vor- und Nachname"), fill(req.sender_address, "Ihre Anschrift")])
    recipient_block = fill(req.recipient or recipient_default, "Behörde und Anschrift laut Schreiben")
    place_date = f"{fill(req.place, 'Ort')}, {fmt(req.letter_date or today)}"
    date_text = fmt(decision_date) if decision_date else fill(None, "Datum des Schreibens")
    ref_text = f", Aktenzeichen {reference}," if reference else ""
    ref_subject = f" – Az. {reference}" if reference else ""

    notes: list[str] = []
    warnings: list[str] = []
    legal: list[Link] = []

    if req.kind == "widerspruch":
        noun = "Einspruch" if remedy == "einspruch" else "Widerspruch"
        subject = f"{noun} gegen den Bescheid vom {date_text}{ref_subject}"
        paragraphs = [f"hiermit lege ich gegen Ihren Bescheid vom {date_text}{ref_text} {noun} ein."]
        if req.reason and req.reason.strip():
            paragraphs.append("Begründung:\n" + req.reason.strip())
        else:
            paragraphs.append("Die Begründung reiche ich gesondert nach.")
        paragraphs.append(f"Bitte bestätigen Sie mir den Eingang dieses {'Einspruchs' if noun == 'Einspruch' else 'Widerspruchs'}.")
        notes = [
            f"Der {noun} muss vor Ablauf der Frist bei der Behörde eingehen. Die Begründung kann später folgen.",
            "Unterschreiben Sie den Brief eigenhändig. Eine einfache E-Mail genügt in der Regel nicht.",
            "Versenden Sie so, dass Sie den Eingang nachweisen können: Einwurf-Einschreiben, Fax mit Sendebericht oder persönliche Abgabe mit Eingangsstempel.",
        ]
        legal = [LAW_LINKS["ao357"]] if noun == "Einspruch" else [LAW_LINKS["sgg84"], LAW_LINKS["vwgo70"]]
        if analysis and not appeal:
            warnings.append("Im Schreiben wurde keine Rechtsbehelfsbelehrung erkannt. Prüfen Sie, ob es sich um einen Bescheid handelt.")
    elif req.kind == "fristverlaengerung":
        subject = f"Bitte um Fristverlängerung – Ihr Schreiben vom {date_text}{ref_subject}"
        until = fmt(req.requested_until) if req.requested_until else fill(None, "gewünschtes neues Datum")
        paragraphs = [
            f"in Ihrem Schreiben vom {date_text}{ref_text} haben Sie mir eine Frist gesetzt. "
            f"Ich bitte Sie, diese Frist bis zum {until} zu verlängern.",
            "Grund:\n" + fill(req.reason, "kurzer Grund, z. B. Unterlagen liegen noch nicht vor"),
            "Für eine kurze Bestätigung wäre ich Ihnen dankbar.",
        ]
        notes = [
            "Senden Sie die Bitte vor Ablauf der ursprünglichen Frist ab. Bis zur Zusage gilt die alte Frist.",
            "Unterschreiben Sie den Brief und bewahren Sie einen Nachweis über den Versand auf.",
        ]
        if appeal:
            warnings.append(
                "Gesetzliche Widerspruchs-, Einspruchs- und Klagefristen lassen sich nicht verlängern. "
                "Wollen Sie den Bescheid angreifen, legen Sie fristgerecht Widerspruch ein und reichen die Begründung nach."
            )
    else:  # nachreichung
        subject = f"Nachreichung von Unterlagen – Ihr Schreiben vom {date_text}{ref_subject}"
        items = [i.strip() for i in req.items if i.strip()]
        if not items and analysis:
            items = [r.text for r in analysis.requirements if r.kind == "document"] or list(analysis.requested_items)
        item_lines = "\n".join(f"• {i}" for i in items) if items else "• " + fill(None, "Liste der beigefügten Unterlagen")
        paragraphs = [
            f"mit Ihrem Schreiben vom {date_text}{ref_text} haben Sie Unterlagen angefordert. Anbei übersende ich:",
            item_lines,
        ]
        if req.reason and req.reason.strip():
            paragraphs.append(req.reason.strip())
        paragraphs.append("Sollten noch Angaben fehlen, geben Sie mir bitte Bescheid.")
        notes = [
            "Schicken Sie Kopien, keine Originale, sofern nicht ausdrücklich Originale verlangt werden.",
            "Notieren Sie Aktenzeichen oder Name auf jeder Seite.",
            "Bewahren Sie einen Nachweis über den Versand auf.",
        ]

    body = "Sehr geehrte Damen und Herren,\n\n" + "\n\n".join(paragraphs) + "\n\nMit freundlichen Grüßen\n\n\n" + sender_block.split("\n")[0]
    full_text = "\n\n".join([sender_block, recipient_block, place_date, subject, body])
    return LetterDraft(
        kind=req.kind,
        title=TITLES[req.kind] if not (req.kind == "widerspruch" and remedy == "einspruch") else "Einspruch",
        sender_block=sender_block,
        recipient_block=recipient_block,
        place_date=place_date,
        subject=subject,
        body=body,
        full_text=full_text,
        missing=fill.missing,
        notes=notes,
        warnings=warnings,
        legal=legal,
    )
