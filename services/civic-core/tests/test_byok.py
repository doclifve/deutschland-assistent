"""Eigener API-Schlüssel pro Anfrage (BYOK) und Anbieter-Adapter."""
import json

import anthropic
import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

import deutschland_assistent.main as main_module
from deutschland_assistent.byok import validate_custom_base_url
from deutschland_assistent.model_provider import (
    AnthropicProvider,
    DisabledModelProvider,
    LLMSettings,
    ModelProviderError,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    build_provider,
)

client = TestClient(main_module.app)
SECRET = "sk-test-SEHR-GEHEIM-123"


@pytest.fixture(autouse=True)
def server_without_llm(monkeypatch):
    monkeypatch.setattr(main_module, "model_provider", DisabledModelProvider())
    for name in ["BYOK_ENABLED", "BYOK_ALLOWED_PROVIDERS", "BYOK_ALLOW_CUSTOM_BASE_URL", "APP_ENV"]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def captured(monkeypatch):
    """Ersetzt den HTTP-Aufruf des OpenAI-kompatiblen Adapters und merkt sich die Konfiguration."""
    calls = []

    async def fake_generate(self, *, system_prompt, user_prompt):
        calls.append(self.config)
        return {"ok": True}

    monkeypatch.setattr(OpenAICompatibleProvider, "structured_generate", fake_generate)
    return calls


def test_providers_listing_hides_custom_by_default():
    body = client.get("/v1/llm/providers").json()
    ids = [p["id"] for p in body["providers"]]
    assert body["server_llm_configured"] is False and body["byok_enabled"] is True
    assert {"ionos", "stackit", "mistral", "anthropic", "openai"} <= set(ids)
    assert "custom" not in ids
    assert next(p for p in body["providers"] if p["id"] == "anthropic")["default_model"] == "claude-opus-5-5"


def test_without_key_and_without_server_llm():
    assert client.post("/v1/llm/test").status_code == 503


def test_own_key_is_used_for_the_request(captured):
    r = client.post("/v1/llm/test", headers={"X-LLM-Provider": "mistral", "X-LLM-Api-Key": SECRET})
    assert r.status_code == 200 and r.json()["ok"] is True
    cfg = captured[0]
    assert cfg.api_key == SECRET
    assert cfg.base_url == "https://api.mistral.ai/v1"
    assert cfg.model == "mistral-large-latest"


def test_own_key_reaches_ask_endpoint(captured):
    r = client.post(
        "/v1/ask",
        json={"message": "Was bedeutet § 60 SGB I?"},
        headers={"X-LLM-Provider": "ionos", "X-LLM-Api-Key": SECRET, "X-LLM-Model": "meta-llama/x"},
    )
    assert r.status_code == 200
    assert captured and captured[0].model == "meta-llama/x"


def test_model_required_for_presets_without_default():
    r = client.post("/v1/llm/test", headers={"X-LLM-Provider": "openai", "X-LLM-Api-Key": SECRET})
    assert r.status_code == 422 and "Modellnamen" in r.json()["detail"]


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"X-LLM-Provider": "anthropic"}, 422),  # Schlüssel fehlt
        ({"X-LLM-Provider": "gibtsnicht", "X-LLM-Api-Key": SECRET}, 422),
        ({"X-LLM-Provider": "custom", "X-LLM-Base-Url": "https://8.8.8.8/v1"}, 422),  # custom nicht freigegeben
        ({"X-LLM-Provider": "mistral", "X-LLM-Api-Key": "a\tb"}, 422),
    ],
)
def test_invalid_byok_headers(headers, status):
    assert client.post("/v1/llm/test", headers=headers).status_code == status


def test_byok_can_be_disabled(monkeypatch):
    monkeypatch.setenv("BYOK_ENABLED", "false")
    r = client.post("/v1/llm/test", headers={"X-LLM-Provider": "mistral", "X-LLM-Api-Key": SECRET})
    assert r.status_code == 403


def test_allowed_provider_list(monkeypatch):
    monkeypatch.setenv("BYOK_ALLOWED_PROVIDERS", "ionos,stackit")
    assert [p["id"] for p in client.get("/v1/llm/providers").json()["providers"]] == ["ionos", "stackit"]
    r = client.post("/v1/llm/test", headers={"X-LLM-Provider": "mistral", "X-LLM-Api-Key": SECRET})
    assert r.status_code == 422


def test_custom_endpoint_when_allowed(monkeypatch, captured):
    monkeypatch.setenv("BYOK_ALLOW_CUSTOM_BASE_URL", "true")
    r = client.post(
        "/v1/llm/test",
        headers={"X-LLM-Provider": "custom", "X-LLM-Base-Url": "https://8.8.8.8/v1", "X-LLM-Model": "m"},
    )
    assert r.status_code == 200
    assert captured[0].base_url == "https://8.8.8.8/v1"


@pytest.mark.parametrize(
    "url,env",
    [
        ("http://8.8.8.8/v1", "development"),  # kein HTTPS
        ("https://10.0.0.5/v1", "development"),  # privates Netz
        ("https://169.254.169.254/latest", "development"),  # Cloud-Metadaten
        ("https://127.0.0.1/v1", "production"),
        ("http://localhost:11434/v1", "production"),
        ("https://user:pw@8.8.8.8/v1", "development"),
    ],
)
def test_custom_url_ssrf_guard(monkeypatch, url, env):
    from fastapi import HTTPException

    monkeypatch.setenv("APP_ENV", env)
    with pytest.raises(HTTPException):
        validate_custom_base_url(url)


def test_localhost_allowed_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert validate_custom_base_url("http://localhost:11434/v1") == "http://localhost:11434/v1"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,text", [(401, "API-Schlüssel ungültig"), (404, "Modell"), (429, "Limit")])
async def test_openai_compatible_error_messages_do_not_leak_key(status, text):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status))) as c:
        provider = OpenAICompatibleProvider(
            OpenAICompatibleConfig(base_url="https://x.test/v1", model="m", api_key=SECRET), client=c, label="Test"
        )
        with pytest.raises(ModelProviderError) as exc:
            await provider.structured_generate(system_prompt="s", user_prompt="u")
    assert text in str(exc.value)
    assert SECRET not in str(exc.value) and exc.value.__cause__ is None


def _anthropic_with(handler):
    sdk = anthropic.AsyncAnthropic(
        api_key=SECRET, max_retries=0, http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    )
    return sdk


def _message(text, stop_reason="end_turn"):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


@pytest.mark.asyncio
async def test_anthropic_request_shape_and_json_parsing():
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return httpx2.Response(200, json=_message('```json\n{"meaning": "x"}\n```'))

    provider = AnthropicProvider(api_key=SECRET, model="claude-opus-5-5", client=_anthropic_with(handler))
    assert await provider.structured_generate(system_prompt="Sys", user_prompt="Frage") == {"meaning": "x"}
    body = seen["body"]
    assert seen["url"].startswith("https://api.anthropic.com/v1/messages")
    assert seen["headers"]["x-api-key"] == SECRET
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
    assert body["max_tokens"] >= 16000
    assert "temperature" not in body and "thinking" not in body
    assert body["messages"] == [{"role": "user", "content": "Frage"}]


@pytest.mark.asyncio
async def test_anthropic_model_without_fallback_support_uses_plain_endpoint():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta")
        return httpx2.Response(200, json=_message('{"a": 1}'))

    provider = AnthropicProvider(api_key=SECRET, model="claude-haiku-5-5", client=_anthropic_with(handler))
    assert await provider.structured_generate(system_prompt="s", user_prompt="u") == {"a": 1}
    assert "fallbacks" not in seen["body"] and not seen["beta"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,text",
    [
        (httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad"}}), "API-Schlüssel ungültig"),
        (httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}), "Limit"),
        (httpx2.Response(200, json=_message("", stop_reason="refusal")), "abgelehnt"),
        (httpx2.Response(200, json=_message("kein json")), "kein gültiges JSON"),
    ],
)
async def test_anthropic_errors(response, text):
    provider = AnthropicProvider(api_key=SECRET, model="claude-opus-5-5", client=_anthropic_with(lambda r: response))
    with pytest.raises(ModelProviderError) as exc:
        await provider.structured_generate(system_prompt="s", user_prompt="u")
    assert text in str(exc.value) and SECRET not in str(exc.value)


def test_env_presets_and_legacy_values():
    assert isinstance(build_provider(LLMSettings(provider="disabled")), DisabledModelProvider)
    p = build_provider(LLMSettings(provider="anthropic", api_key=SECRET))
    assert isinstance(p, AnthropicProvider) and p.model == "claude-opus-5-5"
    legacy = build_provider(LLMSettings(provider="openai_compatible", base_url="https://x.test/v1", model="m"))
    assert isinstance(legacy, OpenAICompatibleProvider)
    with pytest.raises(ModelProviderError):
        build_provider(LLMSettings(provider="mistral"))  # Schlüssel fehlt
