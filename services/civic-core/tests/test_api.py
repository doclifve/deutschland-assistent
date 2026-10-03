from fastapi.testclient import TestClient
from deutschland_assistent.main import app
client=TestClient(app)
def test_health(): assert client.get("/health").json()["status"]=="ok"
def test_law_ref():
 r=client.post("/v1/ask",json={"message":"Was bedeutet § 60 SGB I?"}); assert r.status_code==200; assert r.json()["legal_references"][0]["law"]=="SGB I"
def test_upload_deadline():
 r=client.post("/v1/documents",files={"file":("brief.txt","Bitte bis zum 21.10.2026 antworten. § 60 SGB I.","text/plain")}); assert r.status_code==200; assert r.json()["deadlines"][0]["date"]=="2026-10-21"
