"""Regression tests for crash fixes: unicode download names, atomic confirmation, odd API payloads."""
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from deutschland_assistent.actions import ActionStore, new_action
from deutschland_assistent.evidence import Neuris
from deutschland_assistent.main import app, attachment_headers

from make_form import make_form_pdf

client = TestClient(app)


@pytest.mark.parametrize("name", ["Заявление.pdf", 'Antrag→Wohngeld "x".pdf', "Ärger ü.pdf", "日本.pdf"])
def test_attachment_headers_are_latin1_safe(name):
    header = attachment_headers(name)["Content-Disposition"]
    header.encode("latin-1")  # must not raise
    assert '"' not in header.split('filename="', 1)[1].split('"', 1)[0]
    assert unquote(header.split("filename*=UTF-8''", 1)[1]) == name


def test_artifact_download_with_non_latin_filename():
    inspected = client.post(
        "/v1/forms/inspect", files={"file": ("Заявление.pdf", make_form_pdf(), "application/pdf")}
    )
    assert inspected.status_code == 200
    prepared = client.post(f"/v1/forms/{inspected.json()['form_id']}/prepare", json={"values": {}}).json()
    confirmed = client.post(
        f"/v1/actions/{prepared['action_id']}/confirm", json={"approve": True, "expected_version": 1}
    )
    assert confirmed.status_code == 200
    artifact = client.get(confirmed.json()["artifact_url"])
    assert artifact.status_code == 200
    assert artifact.content.startswith(b"%PDF")


def test_update_action_compare_and_swap():
    store = ActionStore()
    action = new_action("appointment", summary="x", payload={}, execution_target="t", ttl_seconds=60)
    store.put_action(action)
    first = action.model_copy(update={"status": "approved", "version": 2})
    second = action.model_copy(update={"status": "cancelled", "version": 2})
    assert store.update_action(action.action_id, first, expected_version=1)
    assert not store.update_action(action.action_id, second, expected_version=1)
    assert store.get_action(action.action_id).preview.status == "approved"


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], {"member": "kaputt"}])
async def test_unexpected_neuris_payload_raises_value_error(body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as c:
        api = Neuris(client=c, cache_ttl_seconds=0)
        with pytest.raises(ValueError):
            await api.search_legislation("Wohngeld")
        with pytest.raises(ValueError):
            await api.search_case_law("Wohngeld")
