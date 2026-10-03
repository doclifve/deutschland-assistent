import time

import pytest
from fastapi.testclient import TestClient

import deutschland_assistent.main as main_module
from deutschland_assistent.agent_planning import map_profile_to_form
from deutschland_assistent.actions import StoredForm
from deutschland_assistent.main import app
from deutschland_assistent.schemas import FormFieldInfo

client = TestClient(app)


def test_chat_without_llm_still_suggests_appointment():
    response = client.post(
        "/v1/chat",
        json={
            "messages": [
                {"role": "user", "content": "Kannst du mir einen Termin beim Bürgeramt buchen?"}
            ],
            "language": "de",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert any(x["type"] == "appointment" for x in body["suggested_actions"])


def test_appointment_requires_explicit_confirmation():
    prepared = client.post(
        "/v1/actions/appointment",
        json={
            "service": "Personalausweis beantragen",
            "authority": "Bürgeramt",
            "location": "Berlin",
            "official_booking_url": "https://service.berlin.de/",
        },
    )
    assert prepared.status_code == 200
    action = prepared.json()
    assert action["status"] == "prepared"
    assert action["requires_confirmation"] is True

    approved = client.post(
        f"/v1/actions/{action['action_id']}/confirm",
        json={"approve": True, "expected_version": 1},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_appointment_can_be_cancelled():
    prepared = client.post(
        "/v1/actions/appointment",
        json={"service": "Termin beim Amt"},
    ).json()
    cancelled = client.post(
        f"/v1/actions/{prepared['action_id']}/confirm",
        json={"approve": False, "expected_version": 1},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_external_completion_disabled_without_agent_token(monkeypatch):
    prepared = client.post(
        "/v1/actions/appointment",
        json={"service": "Termin beim Amt"},
    ).json()
    approved = client.post(
        f"/v1/actions/{prepared['action_id']}/confirm",
        json={"approve": True, "expected_version": 1},
    ).json()

    monkeypatch.setattr(main_module, "AGENT_EXECUTION_TOKEN", "")
    completed = client.post(
        f"/v1/actions/{approved['action_id']}/complete",
        json={"success": True, "result_summary": "Termin gebucht"},
    )
    assert completed.status_code == 503


@pytest.mark.asyncio
async def test_form_agent_maps_only_existing_fields():
    class FakeProvider:
        enabled = True

        async def structured_generate(self, *, system_prompt, user_prompt):
            return {
                "values": {
                    "vorname": "Ada",
                    "nachname": "Lovelace",
                    "erfunden": "nicht erlaubt",
                },
                "unresolved": ["geburtsdatum", "nicht-vorhanden"],
            }

    result = await map_profile_to_form(
        FakeProvider(),
        fields=[
            FormFieldInfo(name="vorname", label="Vorname"),
            FormFieldInfo(name="nachname", label="Nachname"),
            FormFieldInfo(name="geburtsdatum", label="Geburtsdatum"),
        ],
        profile={"vorname": "Ada", "nachname": "Lovelace"},
    )
    assert result.values == {"vorname": "Ada", "nachname": "Lovelace"}
    assert result.unresolved == ["geburtsdatum"]


def test_form_action_is_filled_only_after_confirmation(monkeypatch):
    form = StoredForm(
        created=time.monotonic(),
        filename="antrag.pdf",
        data=b"%PDF-dummy",
        fields=[FormFieldInfo(name="vorname", label="Vorname")],
    )
    form_id = main_module.ACTION_STORE.put_form(form)

    prepared = client.post(
        f"/v1/forms/{form_id}/prepare",
        json={"values": {"vorname": "Ada"}},
    )
    assert prepared.status_code == 200
    action = prepared.json()
    assert action["status"] == "prepared"

    monkeypatch.setattr(main_module, "fill_pdf_form", lambda data, values: b"%PDF-filled")
    approved = client.post(
        f"/v1/actions/{action['action_id']}/confirm",
        json={"approve": True, "expected_version": 1},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "completed"
    assert body["artifact_url"]

    artifact = client.get(body["artifact_url"])
    assert artifact.status_code == 200
    assert artifact.content == b"%PDF-filled"


def test_action_optimistic_lock_prevents_stale_confirmation():
    prepared = client.post(
        "/v1/actions/appointment",
        json={"service": "Termin"},
    ).json()

    first = client.post(
        f"/v1/actions/{prepared['action_id']}/confirm",
        json={"approve": False, "expected_version": 1},
    )
    assert first.status_code == 200

    stale = client.post(
        f"/v1/actions/{prepared['action_id']}/confirm",
        json={"approve": True, "expected_version": 1},
    )
    assert stale.status_code == 409
