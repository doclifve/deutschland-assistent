import asyncio
from datetime import date

import pytest

from deutschland_assistent.appointments import bundesportal_search_url, match_concern, prepare_appointment
from deutschland_assistent.forms import FormError, SuggestContext, fill_form, match_label, read_form, suggest_by_label, suggest_by_model
from deutschland_assistent.letters import draft_letter, extract_reference
from deutschland_assistent.schemas import AppealInstruction, DocumentAnalysis, LetterRequest, Requirement

from make_form import make_form_pdf


# ---------------------------------------------------------------- appointments

@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ich bin umgezogen und muss mich ummelden", "wohnsitz-anmelden"),
        ("Mein Perso ist abgelaufen", "personalausweis"),
        ("Ich brauche ein Führungszeugnis", "fuehrungszeugnis"),
        ("Auto anmelden", "fahrzeug-zulassen"),
        ("Termin beim Standesamt", None),
    ],
)
def test_match_concern(text, expected):
    found = match_concern(text)
    assert (found["id"] if found else None) == expected


def test_appointment_plan_with_postal_code():
    plan = prepare_appointment("Wohnsitz anmelden", "20095")
    assert plan.concern_id == "wohnsitz-anmelden"
    assert any("Wohnungsgeberbestätigung" in b for b in plan.bring)
    urls = [l.url for l in plan.links]
    assert "https://verwaltung.bund.de/leistungsverzeichnis/de/leistung/99115005104001" in urls
    assert bundesportal_search_url("Wohnsitz Anmeldung", "20095") in urls
    assert any(l.kind == "official_law" and l.url.endswith("/bmg/__17.html") for l in plan.links)
    assert "selbst" in plan.disclaimer


def test_appointment_rejects_invalid_postal_code_and_offers_alternatives():
    plan = prepare_appointment("Hochzeit anmelden beim Standesamt", "abc")
    assert plan.concern_id is None
    assert "postleitzahlOrt" not in plan.links[0].url
    assert plan.alternatives


def test_fuehrungszeugnis_offers_online_route():
    plan = prepare_appointment("Führungszeugnis")
    assert any(l.kind == "online_service" and "fuehrungszeugnis.bund.de" in l.url for l in plan.links)


# --------------------------------------------------------------------- letters

def _decision(**kw):
    base = dict(document_id="d", filename="b.txt", document_type="authority_decision", text_preview="",
                document_date=date(2026, 9, 13), authority_hint="Jobcenter")
    base.update(kw)
    return DocumentAnalysis(**base)


@pytest.mark.parametrize(
    "text,ref",
    [
        ("Unser Zeichen: BG 12345/67 vom", "BG 12345/67"),
        ("Steuernummer 12/345/67890 xyz", "12/345/67890"),
        ("Az. 3 K 123/26 Datum", "3 K 123/26"),
        ("Aktenzeichen: bitte angeben", None),
    ],
)
def test_extract_reference(text, ref):
    assert extract_reference(text) == ref


def test_widerspruch_uses_document_facts_and_marks_gaps():
    analysis = _decision(appeal_instruction=AppealInstruction(remedy="widerspruch", evidence_text="x", recipient="Jobcenter Hamburg"))
    d = draft_letter(LetterRequest(kind="widerspruch", sender_name="Max Muster"), analysis=analysis,
                     document_text="Aktenzeichen: 123-ABC/45\n", today=date(2026, 10, 3))
    assert "Bescheid vom 13.09.2026, Aktenzeichen 123-ABC/45, Widerspruch ein." in d.body
    assert "Begründung reiche ich gesondert nach" in d.body
    assert d.recipient_block == "Jobcenter Hamburg"
    assert d.missing == ["Ihre Anschrift", "Ort"]
    assert "[Ihre Anschrift]" in d.full_text
    assert any("sgg/__84" in l.url for l in d.legal)


def test_einspruch_for_tax_office():
    analysis = _decision(authority_hint="Finanzamt", appeal_instruction=AppealInstruction(remedy="einspruch", evidence_text="x"))
    d = draft_letter(LetterRequest(kind="widerspruch"), analysis=analysis, today=date(2026, 10, 3))
    assert d.title == "Einspruch" and "Einspruch ein." in d.body
    assert any("ao_1977/__357" in l.url for l in d.legal)


def test_extension_warns_that_statutory_deadlines_cannot_be_extended():
    analysis = _decision(appeal_instruction=AppealInstruction(remedy="widerspruch", evidence_text="x"))
    d = draft_letter(LetterRequest(kind="fristverlaengerung", requested_until=date(2026, 11, 2)), analysis=analysis)
    assert "bis zum 02.11.2026" in d.body
    assert d.warnings and "nicht verlängern" in d.warnings[0]


def test_nachreichung_lists_requested_documents_only():
    analysis = _decision(document_type="authority_request", requirements=[
        Requirement(text="Schulbescheinigung", kind="document"),
        Requirement(text="20 Euro überweisen", kind="payment"),
    ])
    d = draft_letter(LetterRequest(kind="nachreichung"), analysis=analysis)
    assert "• Schulbescheinigung" in d.body and "überweisen" not in d.body


# ----------------------------------------------------------------------- forms

@pytest.fixture(scope="module")
def form():
    data = make_form_pdf()
    return data, read_form(data, "f1", "antrag.pdf")


def test_read_form_detects_field_types(form):
    _, info = form
    types = {f.id: f.type for f in info.fields}
    assert types["vorname"] == "text" and types["zustimmung"] == "checkbox"
    assert types["familienstand"] == "radio" and types["bundesland"] == "choice"
    assert {o.text for o in next(f for f in info.fields if f.id == "familienstand").options} == {"ledig", "verheiratet"}


@pytest.mark.parametrize(
    "label,field_id,key",
    [
        ("Familienname", "x", "nachname"),
        ("Geburtsort", "x", "geburtsort"),
        ("Ort, Datum", "x", "datum"),
        ("Wohnort", "x", "ort"),
        ("", "topmostSubform[0].Page1[0].Vorname[0]", "vorname"),
        ("Telefonnummer tagsueber", "Feld_17", "telefon"),
        ("Bemerkungen", "Feld_2", None),
    ],
)
def test_match_label(label, field_id, key):
    assert match_label(label, field_id) == key


def test_suggestions_only_use_given_values(form):
    _, info = form
    ctx = SuggestContext(profile={"vorname": "Erika", "nachname": "Mustermann"}, reference="BG 12345/67", today=date(2026, 10, 3))
    suggestions, unmatched = suggest_by_label(info.fields, ctx)
    by_id = {s.field_id: s for s in suggestions}
    assert by_id["vorname"].value == "Erika"
    assert by_id["az"].value == "BG 12345/67" and by_id["az"].source == "Schreiben"
    assert by_id["datum"].value == "03.10.2026"
    assert "plz" not in by_id and "zustimmung" not in by_id  # no value given / decisions are never pre-ticked
    assert {f.id for f in unmatched} >= {"plz", "ort"}


def test_model_mapping_sees_no_values_and_is_validated(form):
    _, info = form
    seen = {}

    class FakeModel:
        enabled = True

        async def structured_generate(self, *, system_prompt, user_prompt):
            seen["prompt"] = user_prompt
            return {"mapping": {"plz": "plz", "ort": "gehalt", "nope": "vorname"}}

    ctx = SuggestContext(profile={"plz": "20095", "vorname": "Erika"})
    unmatched = [f for f in info.fields if f.id in {"plz", "ort"}]
    out = asyncio.run(suggest_by_model(FakeModel(), unmatched, ctx))
    assert [(s.field_id, s.value, s.matched_by) for s in out] == [("plz", "20095", "model")]
    assert "20095" not in seen["prompt"] and "Erika" not in seen["prompt"]


def test_fill_form_roundtrip(form):
    data, info = form
    radio = next(f for f in info.fields if f.id == "familienstand").options[1].value
    out = fill_form(data, info, {"vorname": "Erika", "zustimmung": True, "familienstand": radio, "bundesland": "Bayern"})
    values = {f.id: f.value for f in read_form(out, "f2", "x.pdf").fields}
    assert values["vorname"] == "Erika" and values["zustimmung"] == "/Yes"
    assert values["familienstand"] == radio and values["bundesland"] == "Bayern"


def test_fill_form_rejects_unknown_fields_and_bad_choices(form):
    data, info = form
    with pytest.raises(FormError):
        fill_form(data, info, {"gibtsnicht": "x"})
    with pytest.raises(FormError):
        fill_form(data, info, {"bundesland": "Atlantis"})


def test_pdf_without_fields_gets_a_hint():
    from reportlab.pdfgen import canvas
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(50, 800, "Kein Formular")
    c.save()
    info = read_form(buf.getvalue(), "f3", "brief.pdf")
    assert info.fields == [] and info.warnings
