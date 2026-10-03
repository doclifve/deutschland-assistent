from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

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


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_tokens: int = 900
    json_mode: bool = True
    region: str | None = None


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
    ):
        if not config.base_url:
            raise ModelProviderError("LLM_BASE_URL fehlt.")
        if not config.model:
            raise ModelProviderError("LLM_MODEL fehlt.")
        self.config = config
        self.client = client

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
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelProviderError("Deutschland-gehostetes Sprachmodell ist nicht erreichbar.") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError("Sprachmodell hat kein erwartetes Antwortformat geliefert.") from exc

        if not isinstance(content, str):
            raise ModelProviderError("Sprachmodell hat keine Textantwort geliefert.")

        cleaned = _strip_code_fence(content)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ModelProviderError("Sprachmodell hat kein gültiges JSON geliefert.") from exc
        if not isinstance(parsed, dict):
            raise ModelProviderError("Sprachmodell-Antwort muss ein JSON-Objekt sein.")
        return parsed


class GermanyHostedProvider(OpenAICompatibleProvider):
    """OpenAI-compatible endpoint explicitly configured as Germany-hosted.

    This class validates configuration, not physical data residency. Operators
    must verify hosting location, subprocessors, retention and DPA separately.
    """

    def __init__(self, config: OpenAICompatibleConfig, *, client: httpx.AsyncClient | None = None):
        if (config.region or "").upper() != "DE":
            raise ModelProviderError("Für LLM_PROVIDER=germany_hosted muss LLM_REGION=DE gesetzt sein.")
        app_env = os.getenv("APP_ENV", "development").lower()
        if app_env == "production" and not config.base_url.lower().startswith("https://"):
            raise ModelProviderError("Deutschland-gehostete LLM-Endpunkte müssen in Produktion HTTPS verwenden.")
        super().__init__(config, client=client)


def build_model_provider() -> ModelProvider:
    provider = os.getenv("LLM_PROVIDER", "disabled").strip().lower()
    if provider in {"", "disabled", "none", "off"}:
        return DisabledModelProvider()

    config = OpenAICompatibleConfig(
        base_url=os.getenv("LLM_BASE_URL", "").strip(),
        model=os.getenv("LLM_MODEL", "").strip(),
        api_key=os.getenv("LLM_API_KEY", "").strip() or None,
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "900")),
        json_mode=_env_bool("LLM_JSON_MODE", True),
        region=os.getenv("LLM_REGION", "").strip() or None,
    )

    if provider == "germany_hosted":
        return GermanyHostedProvider(config)

    if provider in {"openai_compatible", "ollama"}:
        return OpenAICompatibleProvider(config)

    raise ModelProviderError(
        "Unbekannter LLM_PROVIDER. Erlaubt: disabled, germany_hosted, openai_compatible, ollama."
    )


def _strip_code_fence(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, re.S | re.I)
    return match.group(1).strip() if match else value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
