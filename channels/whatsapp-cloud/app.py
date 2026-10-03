import hashlib
import hmac
import logging
import mimetypes
import os
from collections import deque

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
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
MAX_MEDIA_BYTES = int(os.getenv("MAX_WHATSAPP_MEDIA_BYTES", str(15 * 1024 * 1024)))
RECENT_IDS = deque(maxlen=2000)
RECENT_SET: set[str] = set()

if APP_ENV == "production" and (not APP_SECRET or VERIFY == "change-me"):
    raise RuntimeError("In production WHATSAPP_APP_SECRET and a non-default WHATSAPP_VERIFY_TOKEN are required.")
if not APP_SECRET:
    log.warning("WHATSAPP_APP_SECRET not set: webhook signatures are NOT verified (development only).")


def signature_valid(body: bytes, header: str | None, secret: str = APP_SECRET) -> bool:
    if not secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def seen_message(message_id: str | None) -> bool:
    if not message_id:
        return False
    if message_id in RECENT_SET:
        return True
    if len(RECENT_IDS) == RECENT_IDS.maxlen:
        old = RECENT_IDS.popleft()
        RECENT_SET.discard(old)
    RECENT_IDS.append(message_id)
    RECENT_SET.add(message_id)
    return False


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
        log.info("Would send to %s: %s", to, body[:250])
        return
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            f"https://graph.facebook.com/{VER}/{PHONE}/messages",
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body[:4000]}},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        r.raise_for_status()


def format_answer(a: dict) -> str:
    lines = [a.get("what_does_it_mean", "")]
    d = a.get("deadline")
    if d:
        y, m, day = d["date"].split("-")
        hint = " (geschätzt)" if d.get("confidence") == "low" else ""
        lines.append(f"Frist: {day}.{m}.{y}{hint}")
    requirements = a.get("requirements") or []
    if requirements:
        lines.append("Verlangt:\n" + "\n".join("• " + str(x.get("text", "")) for x in requirements[:6]))
    appeal = a.get("appeal_instruction")
    if appeal:
        text = f"Rechtsbehelf erkannt: {str(appeal.get('remedy', '')).upper()}"
        if appeal.get("deadline_expression"):
            text += f"\n{appeal['deadline_expression']}"
        lines.append(text)
    steps = a.get("what_should_i_do", [])
    if steps:
        lines.append("Nächste Schritte:\n" + "\n".join("• " + x for x in steps[:4]))
    sources = [x for x in a.get("sources", []) if x.get("url")][:3]
    if sources:
        lines.append("Amtliche Quellen:\n" + "\n".join(f"• {x.get('title')}\n{x.get('url')}" for x in sources))
    lines.append(a.get("disclaimer", ""))
    return "\n\n".join(x for x in lines if x)


async def download_media(media_id: str) -> tuple[bytes, str, str]:
    if not TOKEN:
        raise RuntimeError("WHATSAPP_ACCESS_TOKEN fehlt.")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        meta = await c.get(f"https://graph.facebook.com/{VER}/{media_id}", headers=headers)
        meta.raise_for_status()
        info = meta.json()
        if int(info.get("file_size") or 0) > MAX_MEDIA_BYTES:
            raise ValueError("WhatsApp-Datei ist zu groß.")
        media = await c.get(info["url"], headers=headers)
        media.raise_for_status()
        if len(media.content) > MAX_MEDIA_BYTES:
            raise ValueError("WhatsApp-Datei ist zu groß.")
    mime = info.get("mime_type") or media.headers.get("content-type") or "application/octet-stream"
    ext = mimetypes.guess_extension(mime.split(";")[0]) or ".bin"
    return media.content, mime, ext


async def analyze_media(message: dict) -> dict:
    media_type = "image" if message.get("image") else "document" if message.get("document") else None
    if not media_type:
        raise ValueError("Keine unterstützte Mediendatei.")
    payload = message[media_type]
    media_id = payload["id"]
    content, mime, ext = await download_media(media_id)
    filename = payload.get("filename") or f"whatsapp-{media_id}{ext}"
    async with httpx.AsyncClient(timeout=180) as c:
        upload = await c.post(CORE + "/v1/documents", files={"file": (filename, content, mime)})
        upload.raise_for_status()
        doc = upload.json()
        caption = payload.get("caption") or "Was bedeutet dieses Schreiben und was muss ich tun?"
        answer = await c.post(
            CORE + "/v1/ask",
            json={"message": caption, "document_id": doc["document_id"], "language": "de"},
        )
        answer.raise_for_status()
        return answer.json()


async def process_message(message: dict) -> None:
    sender = message.get("from")
    if not sender:
        return
    try:
        text = message.get("text", {}).get("body")
        if text:
            async with httpx.AsyncClient(timeout=40) as c:
                r = await c.post(CORE + "/v1/ask", json={"message": text, "language": "de"})
                r.raise_for_status()
                answer = r.json()
        elif message.get("image") or message.get("document"):
            answer = await analyze_media(message)
        else:
            await send(sender, "Aktuell kann ich Text, Fotos und Dokumente lesen.")
            return
        await send(sender, format_answer(answer))
    except Exception:
        log.exception("Message processing failed")
        await send(sender, "Das Dokument konnte gerade nicht verarbeitet werden. Bitte versuchen Sie es erneut oder senden Sie eine PDF-/Foto-Datei.")


@app.post("/webhook")
async def receive(req: Request, background_tasks: BackgroundTasks):
    raw = await req.body()
    if not signature_valid(raw, req.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "Invalid signature")
    payload = await req.json()
    try:
        messages = payload["entry"][0]["changes"][0]["value"].get("messages", [])
    except (KeyError, IndexError, TypeError):
        return {"ok": True, "ignored": True}
    accepted = 0
    for message in messages:
        if seen_message(message.get("id")):
            continue
        background_tasks.add_task(process_message, message)
        accepted += 1
    return {"ok": True, "accepted": accepted}
