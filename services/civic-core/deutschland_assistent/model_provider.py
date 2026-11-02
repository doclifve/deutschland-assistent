"""Austauschbare Sprachmodell-Anbindung.

Der Core funktioniert vollständig ohne Sprachmodell (``LLM_PROVIDER=disabled``). Ist ein Modell konfiguriert –
serverweit über Umgebungsvariablen oder pro Anfrage mit einem eigenen Schlüssel der Nutzerin bzw. des Nutzers
(siehe ``byok.py``) –, dient es nur als Erklärungsschicht hinter der Evidence Engine (MODEL_POLICY.md).

Adapter:
- ``OpenAICompatibleProvider``: jeder Endpunkt mit OpenAI-kompatiblem ``/chat/completions`` (IONOS, STACKIT,
  Mistral, OpenAI, Ollama, eigene Server).
- ``AnthropicProvider``: Claude über das offizielle ``anthropic``-SDK (Messages API).

Kein Adapter protokolliert Prompts, Antworten oder API-Schlüssel.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

import httpx


class ModelProviderError(RuntimeError):
    pass


class ModelProvider(Protocol):
    enabled: bool

    async def structured_generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        ...


class DisabledModelProvider:
    enabled = False

    async def structured_generate(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise ModelProviderError("Sprachmodell ist deaktiviert.")


# --------------------------------------------------------------------------------------------------------------
# Anbieter-Voreinstellungen
# --------------------------------------------------------------------------------------------------------------
ProviderKind = Literal["openai_compatible", "anthropic"]


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    kind: ProviderKind
    base_url: str
    default_model: str | None
    region: str  # "DE", "EU" oder "US" – Sitz der Verarbeitung laut Anbieter; Vertragslage separat prüfen
    key_hint: str
    docs_url: str


PRESETS: dict[str, ProviderPreset] = {
    p.id: p
    for p in [
        ProviderPreset(
            id="ionos",
            label="IONOS AI Model Hub (Deutschland)",
            kind="openai_compatible",
            base_url="https://openai.inference.de-txl.ionos.com/v1",
            default_model="openai/gpt-oss-120b",
            region="DE",
            key_hint="IONOS-Token aus dem Data Center Designer (DCD)",
            docs_url="https://docs.ionos.com/cloud/ai/ai-model-hub",
        ),
        ProviderPreset(
            id="stackit",
            label="STACKIT AI Model Serving (Deutschland)",
            kind="openai_compatible",
            base_url="https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1",
            default_model=None,
            region="DE",
            key_hint="STACKIT AI Model Serving Auth Token",
            docs_url="https://docs.stackit.cloud/products/data-and-ai/ai-model-serving/",
        ),
        ProviderPreset(
            id="mistral",
            label="Mistral AI (EU)",
            kind="openai_compatible",
            base_url="https://api.mistral.ai/v1",
            default_model="mistral-large-latest",
            region="EU",
            key_hint="API-Schlüssel aus console.mistral.ai",
            docs_url="https://docs.mistral.ai/",
        ),
        ProviderPreset(
            id="anthropic",
            label="Anthropic Claude",
            kind="anthropic",
            base_url="https://api.anthropic.com",
            default_model="claude-opus-5-5",
            region="US",
            key_hint="API-Schlüssel aus platform.claude.com (beginnt mit sk-ant-)",
            docs_url="https://platform.claude.com/docs",
        ),
        ProviderPreset(
            id="openai",
            label="OpenAI",
            kind="openai_compatible",
            base_url="https://api.openai.com/v1",
            default_model=None,
            region="US",
            key_hint="API-Schlüssel aus platform.openai.com",
            docs_url="https://platform.openai.com/docs",
        ),
        ProviderPreset(
            id="custom",
            label="Eigener OpenAI-kompatibler Endpunkt",
            kind="openai_compatible",
            base_url="",
            default_model=None,
            region="unbekannt",
            key_hint="Schlüssel Ihres Endpunkts (optional)",
            docs_url="",
        ),
    ]
}


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_tokens: int = 900
    json_mode: bool = True
    region: str | None = None


def _status_message(status: int, provider_label: str) -> str:
    if status in (401, 403):
        return f"{provider_label}: API-Schlüssel ungültig oder ohne Berechtigung."
    if status == 404:
        return f"{provider_label}: Modell oder Endpunkt nicht gefunden – bitte Modellnamen prüfen."
    if status == 429:
        return f"{provider_label}: Anfrage-Limit oder Guthaben erschöpft. Bitte später erneut versuchen."
    if status in (400, 422):
        return f"{provider_label}: Anfrage abgelehnt – passt der Modellname zu diesem Anbieter?"
    return f"{provider_label}: Sprachmodell ist derzeit nicht erreichbar (HTTP {status})."


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ModelProviderError("Sprachmodell hat kein gültiges JSON geliefert.") from exc
    if not isinstance(parsed, dict):
        raise ModelProviderError("Sprachmodell-Antwort muss ein JSON-Objekt sein.")
    return parsed


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible chat-completions adapter.

    The adapter deliberately logs neither prompts nor responses.
    Data residency is a deployment/contract property and cannot be inferred
    reliably from a URL or provider label.
    """

    enabled = True

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        client: httpx.AsyncClient | None = None,
        label: str = "Sprachmodell",
    ):
        if not config.base_url:
            raise ModelProviderError("LLM_BASE_URL fehlt.")
        if not config.model:
            raise ModelProviderError("LLM_MODEL fehlt.")
        self.config = config
        self.client = client
        self.label = label

    @property
    def chat_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    async def structured_generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            if self.client:
                response = await self.client.post(self.chat_url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(self.chat_url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ModelProviderError(_status_message(exc.response.status_code, self.label)) from None
        except (httpx.HTTPError, ValueError):
            # ``from None``: keine Request-Details (inkl. Authorization-Header) in Tracebacks durchreichen.
            raise ModelProviderError(f"{self.label}: Sprachmodell ist nicht erreichbar.") from None

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError("Sprachmodell hat kein erwartetes Antwortformat geliefert.") from exc

        if not isinstance(content, str):
            raise ModelProviderError("Sprachmodell hat keine Textantwort geliefert.")
        return _parse_json_object(content)


class GermanyHostedProvider(OpenAICompatibleProvider):
    """OpenAI-compatible endpoint explicitly configured as Germany-hosted.

    This class validates configuration, not physical data residency. Operators
    must verify hosting location, subprocessors, retention and DPA separately.
    """

    def __init__(self, config: OpenAICompatibleConfig, *, client: httpx.AsyncClient | None = None, label: str = "Sprachmodell"):
        if (config.region or "").upper() != "DE":
            raise ModelProviderError("Für LLM_PROVIDER=germany_hosted muss LLM_REGION=DE gesetzt sein.")
        app_env = os.getenv("APP_ENV", "development").lower()
        if app_env == "production" and not config.base_url.lower().startswith("https://"):
            raise ModelProviderError("Deutschland-gehostete LLM-Endpunkte müssen in Produktion HTTPS verwenden.")
        super().__init__(config, client=client, label=label)


# Modelle, die den serverseitigen Fallback bei Ablehnungen durch Sicherheitsklassifikatoren unterstützen.
_ANTHROPIC_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
# Thinking-Tokens zählen zu max_tokens; zu kleine Werte schneiden die JSON-Antwort ab.
_ANTHROPIC_MIN_MAX_TOKENS = 16000


class AnthropicProvider:
    """Claude über das offizielle ``anthropic``-SDK (Messages API).

    - Adaptives Thinking ist bei aktuellen Modellen Standard; Tiefe über ``effort`` (optional).
    - Keine Sampling-Parameter (``temperature`` wird von aktuellen Modellen abgelehnt).
    - Bei unterstützten Modellen ist der serverseitige Fallback bei Ablehnungen aktiv (``fallbacks: "default"``).
    """

    enabled = True

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int = _ANTHROPIC_MIN_MAX_TOKENS,
        timeout_seconds: float = 60.0,
        effort: str | None = None,
        base_url: str | None = None,
        client: Any | None = None,
        label: str = "Anthropic Claude",
    ):
        if not api_key:
            raise ModelProviderError("Für Anthropic Claude wird ein API-Schlüssel benötigt.")
        if not model:
            raise ModelProviderError("LLM_MODEL fehlt.")
        self.model = model
        self.max_tokens = max(max_tokens, _ANTHROPIC_MIN_MAX_TOKENS)
        self.effort = effort
        self.label = label
        if client is None:
            import anthropic

            client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url=base_url or None,
                timeout=timeout_seconds,
                max_retries=1,
            )
        self.client = client

    async def structured_generate(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        import anthropic

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt + "\n\nAntworte ausschließlich mit einem einzigen JSON-Objekt, ohne Text davor oder danach.",
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        try:
            if self.model in _ANTHROPIC_FALLBACK_MODELS:
                response = await self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                response = await self.client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            raise ModelProviderError(_status_message(401, self.label)) from None
        except anthropic.PermissionDeniedError:
            raise ModelProviderError(_status_message(403, self.label)) from None
        except anthropic.NotFoundError:
            raise ModelProviderError(_status_message(404, self.label)) from None
        except anthropic.RateLimitError:
            raise ModelProviderError(_status_message(429, self.label)) from None
        except anthropic.BadRequestError:
            raise ModelProviderError(_status_message(400, self.label)) from None
        except anthropic.APIStatusError as exc:
            raise ModelProviderError(_status_message(exc.status_code, self.label)) from None
        except anthropic.APIConnectionError:
            raise ModelProviderError(f"{self.label}: Sprachmodell ist nicht erreichbar.") from None

        if getattr(response, "stop_reason", None) == "refusal":
            raise ModelProviderError(f"{self.label}: Das Modell hat die Anfrage abgelehnt.")
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ModelProviderError(f"{self.label}: Antwort wurde abgeschnitten (max_tokens zu klein).")
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        if not text.strip():
            raise ModelProviderError("Sprachmodell hat keine Textantwort geliefert.")
        return _parse_json_object(text)


# --------------------------------------------------------------------------------------------------------------
# Aufbau aus Einstellungen (Server-Umgebung oder eigener Schlüssel pro Anfrage)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LLMSettings:
    provider: str
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_tokens: int = 900
    json_mode: bool = True
    region: str | None = None
    effort: str | None = None


def build_provider(settings: LLMSettings) -> ModelProvider:
    """Erzeugt einen Adapter aus Einstellungen. ``provider`` ist eine Preset-ID oder ein Legacy-Wert."""
    provider = settings.provider.strip().lower()
    if provider in {"", "disabled", "none", "off"}:
        return DisabledModelProvider()

    if provider in {"germany_hosted", "openai_compatible", "ollama"}:
        config = OpenAICompatibleConfig(
            base_url=(settings.base_url or "").strip(),
            model=(settings.model or "").strip(),
            api_key=settings.api_key or None,
            timeout_seconds=settings.timeout_seconds,
            max_tokens=settings.max_tokens,
            json_mode=settings.json_mode,
            region=settings.region,
        )
        if provider == "germany_hosted":
            return GermanyHostedProvider(config)
        return OpenAICompatibleProvider(config)

    preset = PRESETS.get(provider)
    if not preset:
        raise ModelProviderError(
            "Unbekannter LLM_PROVIDER. Erlaubt: disabled, germany_hosted, openai_compatible, ollama, "
            + ", ".join(PRESETS)
            + "."
        )
    model = (settings.model or "").strip() or preset.default_model or ""
    if not model:
        raise ModelProviderError(f"{preset.label}: Bitte einen Modellnamen angeben.")
    base_url = (settings.base_url or "").strip() if preset.id == "custom" else preset.base_url

    if preset.kind == "anthropic":
        return AnthropicProvider(
            api_key=settings.api_key or "",
            model=model,
            max_tokens=settings.max_tokens,
            timeout_seconds=settings.timeout_seconds,
            effort=settings.effort,
            label=preset.label,
        )
    if preset.id != "custom" and not settings.api_key:
        raise ModelProviderError(f"{preset.label}: Bitte einen API-Schlüssel angeben.")
    return OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url=base_url,
            model=model,
            api_key=settings.api_key or None,
            timeout_seconds=settings.timeout_seconds,
            max_tokens=settings.max_tokens,
            json_mode=settings.json_mode,
            region=preset.region,
        ),
        label=preset.label,
    )


def settings_from_env() -> LLMSettings:
    return LLMSettings(
        provider=os.getenv("LLM_PROVIDER", "disabled"),
        base_url=os.getenv("LLM_BASE_URL", "").strip() or None,
        model=os.getenv("LLM_MODEL", "").strip() or None,
        api_key=os.getenv("LLM_API_KEY", "").strip() or None,
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "900")),
        json_mode=_env_bool("LLM_JSON_MODE", True),
        region=os.getenv("LLM_REGION", "").strip() or None,
        effort=os.getenv("LLM_EFFORT", "").strip() or None,
    )


def build_model_provider() -> ModelProvider:
    """Serverweiter Standard-Provider aus den Umgebungsvariablen."""
    return build_provider(settings_from_env())


def with_overrides(settings: LLMSettings, **changes: Any) -> LLMSettings:
    return replace(settings, **changes)


def _strip_code_fence(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, re.S | re.I)
    return match.group(1).strip() if match else value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
