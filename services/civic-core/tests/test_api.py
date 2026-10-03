from fastapi.testclient import TestClient
from deutschland_assistent.main import app
client=TestClient(app)
def test_health(): assert client.get("/health").json()["status"]=="ok"
def test_law_ref():
 r=client.post("/v1/ask",json={"message":"Was bedeutet § 60 SGB I?"}); assert r.status_code==200; assert r.json()["legal_references"][0]["law"]=="SGB I"
def test_upload_deadline():
 r=client.post("/v1/documents",files={"file":("brief.txt","Bitte bis zum 21.10.2026 antworten. § 60 SGB I.","text/plain")}); assert r.status_code==200; assert r.json()["deadlines"][0]["date"]=="2026-10-21"
BESCHEID="Hamburg, den 13.09.2026\nBescheid\nGegen diesen Bescheid kann innerhalb eines Monats nach seiner Bekanntgabe Widerspruch erhoben werden."
def test_relative_deadline_in_answer():
 d=client.post("/v1/documents",files={"file":("bescheid.txt",BESCHEID,"text/plain")}).json()
 assert d["document_date"]=="2026-09-13"; assert d["relative_deadlines"][0]["estimated_end"]=="2026-10-19"
 a=client.post("/v1/ask",json={"message":"Was muss ich tun?","document_id":d["document_id"]}).json()
 assert a["deadline"]["date"]=="2026-10-19"; assert a["deadline"]["confidence"]=="low"
def test_delete_document():
 d=client.post("/v1/documents",files={"file":("brief.txt","Hallo","text/plain")}).json()
 assert client.delete(f"/v1/documents/{d['document_id']}").status_code==204
 assert client.post("/v1/ask",json={"message":"x","document_id":d["document_id"]}).status_code==404
def test_cors_not_wildcard():
 r=client.options("/v1/ask",headers={"Origin":"https://evil.example","Access-Control-Request-Method":"POST"})
 assert r.headers.get("access-control-allow-origin")!="*"
def test_channels_endpoint_without_number(monkeypatch):
 monkeypatch.delenv("WHATSAPP_PUBLIC_NUMBER",raising=False)
 r=client.get("/v1/channels"); assert r.status_code==200; assert r.json()["whatsapp"]["enabled"] is False
def test_channels_endpoint_with_number(monkeypatch):
 monkeypatch.setenv("WHATSAPP_PUBLIC_NUMBER","+49 151 23456789")
 wa=client.get("/v1/channels").json()["whatsapp"]; assert wa["enabled"] is True; assert wa["link"].startswith("https://wa.me/4915123456789")
 assert "token" not in str(wa).lower()


# --- chat, appointments, letters, forms -------------------------------------------------

import deutschland_assistent.main as core
from deutschland_assistent.schemas import EvidenceBundle
from make_form import make_form_pdf


def _offline_evidence(monkeypatch):
    async def collect(query, *a, **k):
        return EvidenceBundle(query=query, items=[], warnings=[])
    monkeypatch.setattr(core.engine, "collect", collect)


def test_chat_endpoint_with_document_suggests_letters(monkeypatch):
    _offline_evidence(monkeypatch)
    text = ("Jobcenter Hamburg\nHamburg, den 13.09.2026\nAktenzeichen: 123-ABC/45\nBescheid\nRechtsbehelfsbelehrung\n"
            "Gegen diesen Bescheid kann innerhalb eines Monats nach seiner Bekanntgabe Widerspruch erhoben werden.")
    doc = client.post("/v1/documents", files={"file": ("bescheid.txt", text, "text/plain")}).json()
    r = client.post("/v1/chat", json={"document_id": doc["document_id"], "messages": [
        {"role": "user", "content": "Was ist das?"},
        {"role": "assistant", "content": "Ein Bescheid."},
        {"role": "user", "content": "Bis wann kann ich widersprechen?"},
    ]})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] and body["answer"]["deadline"]
    assert any(a["kind"] == "letter" and a["params"]["letter"] == "widerspruch" for a in body["actions"])

    letter = client.post("/v1/letters/draft", json={"kind": "widerspruch", "document_id": doc["document_id"]}).json()
    assert "13.09.2026" in letter["subject"] and "123-ABC/45" in letter["subject"]


def test_chat_requires_a_user_message():
    r = client.post("/v1/chat", json={"messages": [{"role": "assistant", "content": "Hallo"}]})
    assert r.status_code == 422


def test_appointment_endpoint():
    r = client.post("/v1/appointments/prepare", json={"concern": "Personalausweis beantragen", "postal_code": "80331"})
    plan = r.json()
    assert r.status_code == 200 and plan["concern_id"] == "personalausweis"
    assert any("postleitzahlOrt=80331" in l["url"] for l in plan["links"])


def test_form_upload_suggest_fill_delete():
    info = client.post("/v1/forms", files={"file": ("antrag.pdf", make_form_pdf(), "application/pdf")}).json()
    form_id = info["form_id"]
    assert {f["id"] for f in info["fields"]} >= {"vorname", "zustimmung"}
    sug = client.post(f"/v1/forms/{form_id}/suggest", json={"profile": {"vorname": "Erika", "iban": "DE00"}, "use_model_for_mapping": False}).json()
    assert {s["field_id"]: s["value"] for s in sug["suggestions"]}["vorname"] == "Erika"
    assert all(s["value"] != "DE00" for s in sug["suggestions"])  # unknown profile keys are ignored
    pdf = client.post(f"/v1/forms/{form_id}/fill", json={"values": {"vorname": "Erika", "zustimmung": True}})
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert client.post(f"/v1/forms/{form_id}/fill", json={"values": {"bundesland": "Atlantis"}}).status_code == 422
    assert client.delete(f"/v1/forms/{form_id}").status_code == 204
    assert client.post(f"/v1/forms/{form_id}/suggest", json={}).status_code == 404
