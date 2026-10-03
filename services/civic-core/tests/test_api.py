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
