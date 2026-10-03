"""Build a small AcroForm PDF for tests (no binary fixtures in the repo)."""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_form_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "Antrag (Testformular)")
    form = c.acroForm
    c.setFont("Helvetica", 10)
    rows = [
        ("vorname", "Vorname", None),
        ("nachname", "Familienname", None),
        ("strasse", "Strasse", None),
        ("plz", "Postleitzahl", None),
        ("ort", "Wohnort", None),
        ("gebdat", "Geburtsdatum", None),
        ("az", "Aktenzeichen", None),
        ("Feld_17", "Feld 17", "Telefonnummer tagsueber"),
        ("datum", "Datum", None),
    ]
    y = 760
    for name, label, tooltip in rows:
        c.drawString(50, y + 4, label)
        form.textfield(name=name, tooltip=tooltip or label, x=200, y=y, width=250, height=18, borderStyle="inset", forceBorder=True)
        y -= 32
    c.drawString(50, y + 4, "Ich bestaetige die Angaben")
    form.checkbox(name="zustimmung", tooltip="Bestaetigung", x=200, y=y, size=14, buttonStyle="check")
    y -= 32
    c.drawString(50, y + 4, "Familienstand")
    for i, val in enumerate(["ledig", "verheiratet"]):
        form.radio(name="familienstand", tooltip="Familienstand", value=val, selected=False, x=200 + i * 90, y=y, size=14)
        c.drawString(218 + i * 90, y + 3, val)
    y -= 32
    c.drawString(50, y + 4, "Bundesland")
    form.choice(name="bundesland", tooltip="Bundesland", value="Hamburg", options=["Berlin", "Hamburg", "Bayern"], x=200, y=y, width=150, height=18)
    c.save()
    return buf.getvalue()
