from fastapi.testclient import TestClient

from deutschland_assistent.main import app

from make_form import make_form_pdf

client = TestClient(app)


def test_appointment_planner_endpoint():
    response = client.post(
        "/v1/appointments/prepare",
        json={"concern": "Personalausweis beantragen", "postal_code": "20095"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["concern_id"] == "personalausweis"
    assert body["links"]


def test_letter_draft_endpoint_from_document():
    text = (
        "Jobcenter Hamburg\n"
        "Hamburg, den 13.09.2026\n"
        "Aktenzeichen: 123-ABC/45\n"
        "Bescheid\n"
        "Rechtsbehelfsbelehrung\n"
        "Gegen diesen Bescheid kann innerhalb eines Monats nach Bekanntgabe Widerspruch erhoben werden."
    )
    doc = client.post(
        "/v1/documents",
        files={"file": ("bescheid.txt", text, "text/plain")},
    ).json()
    response = client.post(
        "/v1/letters/draft",
        json={"kind": "widerspruch", "document_id": doc["document_id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "Widerspruch" in body["title"]
    assert "123-ABC/45" in body["subject"]


def test_richer_form_flow_upload_suggest_fill_delete():
    info_response = client.post(
        "/v1/forms",
        files={"file": ("antrag.pdf", make_form_pdf(), "application/pdf")},
    )
    assert info_response.status_code == 200
    info = info_response.json()
    form_id = info["form_id"]
    assert any(field["id"] == "vorname" for field in info["fields"])

    suggestions = client.post(
        f"/v1/forms/{form_id}/suggest",
        json={
            "profile": {"vorname": "Erika", "iban": "DE00"},
            "use_model_for_mapping": False,
        },
    )
    assert suggestions.status_code == 200
    by_field = {x["field_id"]: x["value"] for x in suggestions.json()["suggestions"]}
    assert by_field["vorname"] == "Erika"
    assert "DE00" not in by_field.values()

    pdf = client.post(
        f"/v1/forms/{form_id}/fill",
        json={"values": {"vorname": "Erika", "zustimmung": True}},
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    assert client.delete(f"/v1/forms/{form_id}").status_code == 204
