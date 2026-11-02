"""Chat ohne Sprachmodell: erkannte Wünsche führen zu vorbelegten, bestätigungspflichtigen Aktionen."""
import pytest
from fastapi.testclient import TestClient

import deutschland_assistent.main as main_module
from deutschland_assistent.model_provider import DisabledModelProvider

client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(main_module, "model_provider", DisabledModelProvider())


def ask(text):
    return client.post("/v1/chat", json={"messages": [{"role": "user", "content": text}]}).json()


@pytest.mark.parametrize(
    "text,service",
    [
        ("Buche mir einen Termin beim Bürgeramt Berlin für einen neuen Personalausweis", "Personalausweis beantragen"),
        ("Ich brauche einen Termin zum Ummelden nach dem Umzug", "Wohnsitz anmelden"),
    ],
)
def test_appointment_wish_is_prefilled(text, service):
    body = ask(text)
    action = body["suggested_actions"][0]
    assert action["type"] == "appointment" and action["prefill"] == {"service": service}
    assert "Termin vorbereiten" in body["message"] and "buchen müssen Sie dort selbst" in body["message"]
    assert "benötigt ein Sprachmodell" not in body["message"]


def test_unknown_appointment_has_no_prefill():
    action = ask("Kannst du mir einen Termin buchen?")["suggested_actions"][0]
    assert action["type"] == "appointment" and action["prefill"] == {}


def test_form_wish_points_to_assistant():
    body = ask("Hilf mir das Formular auszufüllen")
    assert body["suggested_actions"][0]["type"] == "form_fill"
    assert "„Formular ausfüllen“" in body["message"]


def test_without_wish_hints_at_own_key():
    body = ask("Wie wird das Wetter?")
    assert body["suggested_actions"] == []
    assert "eigenen KI-Schlüssel" in body["message"]
