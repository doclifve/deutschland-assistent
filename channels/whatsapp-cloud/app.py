import hashlib
import hmac
import logging
import os

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

log = logging.getLogger("whatsapp-adapter")
app = FastAPI(title="Deutschland Assistent WhatsApp Adapter")

CORE = os.getenv("CIVIC_CORE_URL", "http://localhost:8000")
VERIFY = os.getenv("WHATSAPP_VERIFY_TOKEN", "change-me")
TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
PHONE = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
VER = os.getenv("WHATSAPP_GRAPH_VERSION", "v22.0")
APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
APP_ENV = os.getenv("APP_ENV", "development")

if APP_ENV == "production" and (not APP_SECRET or VERIFY == "change-me"):
    raise RuntimeError("In production WHATSAPP_APP_SECRET and a non-default WHATSAPP_VERIFY_TOKEN are required.")
if not APP_SECRET:
    log.warning("WHATSAPP_APP_SECRET not set: webhook signatures are NOT verified (development only).")


def signature_valid(body: bytes, header: str | None, secret: str = APP_SECRET) -> bool:
    """Meta signs every webhook payload with HMAC-SHA256 of the app secret (X-Hub-Signature-256)."""
    if not secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/webhook", response_class=PlainTextResponse)
def verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token and hmac.compare_digest(hub_verify_token, VERIFY) and hub_challenge:
        return hub_challenge
    raise HTTPException(403, "Webhook verification failed")


async def send(to: str, body: str) -> None:
    if not (TOKEN and PHONE):
        return
    async with httpx.AsyncClient(timeout=20) as c:
        await c.post(
            f"https://graph.facebook.com/{VER}/{PHONE}/messages",
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body[:4000]}},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )


def format_answer(a: dict) -> str:
    lines = [a.get("what_does_it_mean", "")]
    lines += ["• " + x for x in a.get("what_should_i_do", [])[:4]]
    d = a.get("deadline")
    if d:
        y, m, day = d["date"].split("-")
        hint = " (geschätzt)" if d.get("confidence") == "low" else ""
        lines.append(f"Frist: {day}.{m}.{y}{hint}")
    lines.append(a.get("disclaimer", ""))
    return "\n\n".join(x for x in lines if x)


@app.post("/webhook")
async def receive(req: Request):
    raw = await req.body()
    if not signature_valid(raw, req.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "Invalid signature")
    p = await req.json()
    try:
        m = p["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = m["from"]
        text = m.get("text", {}).get("body")
    except (KeyError, IndexError, TypeError):
        return {"ok": True, "ignored": True}
    if not text:
        return {"ok": True, "media_pending": True}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(CORE + "/v1/ask", json={"message": text, "language": "de"})
        a = r.json()
    await send(sender, format_answer(a))
    return {"ok": True}
