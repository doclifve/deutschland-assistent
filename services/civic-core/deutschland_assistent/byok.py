"""Eigener API-Schlüssel pro Anfrage ("Bring your own key").

Nutzerinnen und Nutzer können ein eigenes Sprachmodell-Konto verwenden, ohne dass der Betreiber einen Schlüssel
hinterlegt. Der Schlüssel wird nur für die jeweilige Anfrage im Arbeitsspeicher verwendet: nicht gespeichert,
nicht geloggt, nicht an andere Dienste weitergegeben.

Header:
    X-LLM-Provider   Preset-ID (ionos, stackit, mistral, anthropic, openai, custom)
    X-LLM-Api-Key    API-Schlüssel
    X-LLM-Model      optional – sonst Standardmodell des Presets
    X-LLM-Base-Url   nur bei ``custom`` und nur, wenn der Betreiber eigene Endpunkte erlaubt

Betreiber-Einstellungen:
    BYOK_ENABLED=true                    eigene Schlüssel grundsätzlich erlauben
    BYOK_ALLOWED_PROVIDERS=              Komma-Liste erlaubter Presets (leer = alle außer custom)
    BYOK_ALLOW_CUSTOM_BASE_URL=false     ``custom`` mit beliebiger URL erlauben (Risiko: Server-Side Request Forgery)
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from .model_provider import (
    PRESETS,
    ModelProvider,
    ModelProviderError,
    build_provider,
    settings_from_env,
    with_overrides,
)

MAX_KEY_LENGTH = 512
MAX_MODEL_LENGTH = 200


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def byok_enabled() -> bool:
    return _env_bool("BYOK_ENABLED", True)


def custom_base_url_allowed() -> bool:
    return _env_bool("BYOK_ALLOW_CUSTOM_BASE_URL", False)


def allowed_providers() -> list[str]:
    raw = os.getenv("BYOK_ALLOWED_PROVIDERS", "").strip()
    if raw:
        ids = [p.strip().lower() for p in raw.split(",") if p.strip().lower() in PRESETS]
    else:
        ids = [p for p in PRESETS if p != "custom"]
    if "custom" in ids and not custom_base_url_allowed():
        ids.remove("custom")
    if custom_base_url_allowed() and "custom" not in ids and not raw:
        ids.append("custom")
    return ids


def _is_development() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() != "production"


def validate_custom_base_url(url: str) -> str:
    """Erlaubt nur öffentliche HTTPS-Endpunkte. In der Entwicklung zusätzlich http://localhost (z. B. Ollama)."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if not host or parts.username or parts.password:
        raise HTTPException(422, "Ungültige Endpunkt-URL.")
    local_dev = _is_development() and host in {"localhost", "127.0.0.1", "::1"}
    if parts.scheme != "https" and not (local_dev and parts.scheme == "http"):
        raise HTTPException(422, "Eigene Endpunkte müssen HTTPS verwenden.")
    if local_dev:
        return url.strip()
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except OSError:
        raise HTTPException(422, "Endpunkt-Host konnte nicht aufgelöst werden.") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise HTTPException(422, "Endpunkte in internen oder privaten Netzen sind nicht erlaubt.")
    return url.strip()


def _clean_header(value: str | None, limit: int, name: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > limit or not value.isprintable() or not value.isascii():
        raise HTTPException(422, f"Ungültiger Wert im Header {name}.")
    return value


def provider_from_headers(request: Request) -> ModelProvider | None:
    """Baut einen Provider aus den X-LLM-*-Headern. ``None``, wenn keine eigenen Zugangsdaten gesendet wurden."""
    provider_id = _clean_header(request.headers.get("x-llm-provider"), 40, "X-LLM-Provider")
    api_key = _clean_header(request.headers.get("x-llm-api-key"), MAX_KEY_LENGTH, "X-LLM-Api-Key")
    if not provider_id and not api_key:
        return None
    if not byok_enabled():
        raise HTTPException(403, "Eigene API-Schlüssel sind auf diesem Server deaktiviert.")
    provider_id = (provider_id or "").lower()
    if provider_id not in allowed_providers():
        raise HTTPException(422, f"Anbieter nicht erlaubt. Erlaubt: {', '.join(allowed_providers())}.")
    model = _clean_header(request.headers.get("x-llm-model"), MAX_MODEL_LENGTH, "X-LLM-Model")
    base_url = None
    if provider_id == "custom":
        raw_url = _clean_header(request.headers.get("x-llm-base-url"), 500, "X-LLM-Base-Url")
        if not raw_url:
            raise HTTPException(422, "Für einen eigenen Endpunkt fehlt X-LLM-Base-Url.")
        base_url = validate_custom_base_url(raw_url)
    elif not api_key:
        raise HTTPException(422, "X-LLM-Api-Key fehlt.")

    server = settings_from_env()
    settings = with_overrides(
        server,
        provider=provider_id,
        api_key=api_key,
        model=model,
        base_url=base_url,
        region=None,
    )
    try:
        return build_provider(settings)
    except ModelProviderError as exc:
        raise HTTPException(422, str(exc)) from None


def providers_info(server_provider: ModelProvider) -> dict:
    allowed = allowed_providers()
    return {
        "server_llm_configured": bool(getattr(server_provider, "enabled", False)),
        "byok_enabled": byok_enabled(),
        "custom_base_url_allowed": custom_base_url_allowed(),
        "providers": [
            {
                "id": p.id,
                "label": p.label,
                "kind": p.kind,
                "region": p.region,
                "default_model": p.default_model,
                "model_required": p.default_model is None,
                "key_hint": p.key_hint,
                "docs_url": p.docs_url,
            }
            for p in PRESETS.values()
            if p.id in allowed
        ],
    }
