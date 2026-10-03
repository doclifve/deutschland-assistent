"""Public channel configuration exposed to clients (web app, QR codes).

Only the public WhatsApp number is read here. Access tokens and secrets stay in
the WhatsApp adapter and are never exposed through the API.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from urllib.parse import quote

from .schemas import ChannelsInfo, WhatsAppChannel

DEFAULT_GREETING = "Hallo"


def whatsapp_channel(env: Mapping[str, str] | None = None) -> WhatsAppChannel:
    env = os.environ if env is None else env
    raw = (env.get("WHATSAPP_PUBLIC_NUMBER") or "").strip()
    greeting = (env.get("WHATSAPP_GREETING") or DEFAULT_GREETING).strip()[:200] or DEFAULT_GREETING
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    # E.164: country code + subscriber number, at most 15 digits. wa.me needs no "+" or leading zeros.
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        return WhatsAppChannel(enabled=False, greeting=greeting)
    return WhatsAppChannel(
        enabled=True,
        display_number=raw if raw.startswith("+") else "+" + digits,
        link=f"https://wa.me/{digits}?text={quote(greeting)}",
        greeting=greeting,
    )


def channels_info(env: Mapping[str, str] | None = None) -> ChannelsInfo:
    return ChannelsInfo(whatsapp=whatsapp_channel(env))
