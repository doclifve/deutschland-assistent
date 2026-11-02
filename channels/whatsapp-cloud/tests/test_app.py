import hashlib
import hmac
import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
wa = importlib.import_module("app")


def test_extract_messages_from_all_entries_and_changes():
    payload = {
        "entry": [
            {"changes": [{"value": {"messages": [{"id": "a"}]}}, {"value": {"statuses": []}}]},
            {"changes": [{"value": {"messages": [{"id": "b"}, {"id": "c"}]}}]},
        ]
    }
    assert [m["id"] for m in wa.extract_messages(payload)] == ["a", "b", "c"]


def test_extract_messages_ignores_malformed_payloads():
    assert wa.extract_messages([]) == []
    assert wa.extract_messages({"entry": "x"}) == []
    assert wa.extract_messages({"entry": [{"changes": [None, {"value": {"messages": ["x"]}}]}]}) == []


def test_signature_validation():
    body = b'{"x":1}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert wa.signature_valid(body, sig, "secret")
    assert not wa.signature_valid(body, "sha256=deadbeef", "secret")
    assert not wa.signature_valid(body, None, "secret")


def test_greeting_detection():
    assert wa.is_greeting(" Hallo! ")
    assert not wa.is_greeting("Hallo, was bedeutet § 60 SGB I?")


def test_webhook_rejects_invalid_json_and_accepts_batched_messages(monkeypatch):
    processed = []

    async def fake_process(message):
        processed.append(message["id"])

    monkeypatch.setattr(wa, "process_message", fake_process)
    client = TestClient(wa.app)
    assert client.post("/webhook", content=b"not json").status_code == 400
    body = {
        "entry": [
            {"changes": [{"value": {"messages": [{"id": "m1", "from": "49"}]}}]},
            {"changes": [{"value": {"messages": [{"id": "m2", "from": "49"}]}}]},
        ]
    }
    r = client.post("/webhook", content=json.dumps(body))
    assert r.json() == {"ok": True, "accepted": 2}
    assert processed == ["m1", "m2"]
    # duplicates are ignored
    assert client.post("/webhook", content=json.dumps(body)).json()["accepted"] == 0


def test_format_answer_contains_deadline_and_sources():
    text = wa.format_answer(
        {
            "what_does_it_mean": "Erklärung",
            "deadline": {"date": "2026-12-01", "confidence": "low"},
            "sources": [{"title": "SGB I", "url": "https://www.gesetze-im-internet.de/sgb_1/"}],
        }
    )
    assert "Frist: 01.12.2026 (geschätzt)" in text
    assert "gesetze-im-internet.de" in text
