"""Ende-zu-Ende-Video: „Buche mir einen Termin …“ in der echten App (docs/media/<NAME>.mp4 und .gif).

Anders als die gerenderten Filme ist das eine Aufnahme der laufenden Anwendung: Chat, Vorschlag, Terminkarte,
Prüfung der Buchungsseite, Bestätigung und Weiterleitung. Eingeblendet werden nur Bildunterschriften und ein
Mauszeiger. Die amtliche Buchungsseite am Ende wird nicht nachgebaut, sondern als gekennzeichneter Platzhalter
gezeigt.

Voraussetzungen: laufender Stack ohne Sprachmodell (API :8000, Web :3000 als Produktions-Build), Python mit
`playwright`, ffmpeg.

    make dev            # oder: API + `npm run build && npx next start` in apps/web
    python docs/media/termin/record.py
    # optional: CHROMIUM_EXECUTABLE=/pfad/zu/chrome, WEB_URL=http://localhost:3000
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.async_api import Page, async_playwright

OUT = Path(__file__).resolve().parent.parent
NAME = "termin-ende-zu-ende-v1"  # bei Änderungen hochzählen (Cache von GitHub und Browsern)
WEB = os.getenv("WEB_URL", "http://localhost:3000")
SIZE = {"width": 860, "height": 760}
BOOKING_URL = "https://service.berlin.de/"

OVERLAY_JS = r"""
() => {
  if (document.getElementById('demo-cap')) return;
  const css = document.createElement('style');
  css.textContent = `
    #demo-cap { position: fixed; left: 50%; top: 18px; transform: translateX(-50%); z-index: 2147483000; display: flex; gap: 14px;
      align-items: center; max-width: 800px; padding: 14px 22px; border-radius: 22px; background: rgba(255,255,255,.96);
      box-shadow: 0 16px 40px rgba(0,0,0,.16); font: 600 20px/1.3 -apple-system, "Helvetica Neue", "Inter", sans-serif;
      color: #1D1D1F; transition: opacity .35s; opacity: 0; }
    #demo-cap b { flex: none; display: inline-flex; width: 36px; height: 36px; border-radius: 50%; background: #1D1D1F; color: #fff;
      align-items: center; justify-content: center; font-size: 18px; }
    #demo-cap b.gold { background: #FFCC00; color: #1D1D1F; }
    #demo-cursor { position: fixed; left: 430px; top: 700px; width: 24px; height: 24px; margin: -12px 0 0 -12px; z-index: 2147483001;
      border-radius: 50%; background: rgba(221,0,0,.85); box-shadow: 0 0 0 4px rgba(255,255,255,.9), 0 6px 16px rgba(0,0,0,.3);
      transition: left .65s cubic-bezier(.4,0,.2,1), top .65s cubic-bezier(.4,0,.2,1), transform .15s; pointer-events: none; }
    #demo-card { position: fixed; inset: 0; z-index: 2147483002; background: #fff; display: flex; flex-direction: column;
      align-items: center; justify-content: center; text-align: center; transition: opacity .5s; font-family: -apple-system, "Helvetica Neue", "Inter", sans-serif; }
    #demo-card .cl { position: relative; width: 112px; height: 98px; }
    #demo-card .cl span { position: absolute; width: 60px; height: 60px; border-radius: 50%; }
    #demo-card h1 { margin: 34px 24px 0; font-size: 50px; letter-spacing: -0.035em; line-height: 1.05; color: #1D1D1F; }
    #demo-card p { margin: 18px 40px 0; font-size: 22px; line-height: 1.4; color: #636366; }`;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'demo-cap'; document.body.appendChild(cap);
  const cur = document.createElement('div'); cur.id = 'demo-cursor'; document.body.appendChild(cur);
}
"""

PLACEHOLDER = """<!doctype html><html lang="de"><meta charset="utf-8"><title>Platzhalter</title>
<body style="margin:0;background:#F5F5F7;font-family:-apple-system,'Helvetica Neue','Inter',sans-serif;color:#1D1D1F">
<div style="margin:150px auto 0;max-width:640px;background:#fff;border-radius:28px;padding:40px 44px;box-shadow:0 30px 70px rgba(0,0,0,.12)">
<div style="font-size:18px;color:#636366;font-weight:600">Weitergeleitet zu</div>
<div style="margin-top:6px;font-size:30px;font-weight:700;letter-spacing:-.02em">{url}</div>
<p style="margin:22px 0 0;font-size:22px;line-height:1.45">Hier öffnet sich die <b>amtliche Buchungsseite</b> der Behörde.
Den Termin wählen und buchen Sie dort selbst.</p>
<p style="margin:22px 0 0;font-size:16px;color:#8E8E93">Platzhalter im Erklärvideo – die echte Seite wird hier weder geladen noch nachgebildet.</p>
</div></body></html>"""


async def caption(page: Page, step: str, text: str, gold: bool = False) -> None:
    await page.evaluate(OVERLAY_JS)
    await page.evaluate(
        """([s, t, g]) => { const c = document.getElementById('demo-cap');
             c.innerHTML = (s ? `<b class="${g ? 'gold' : ''}">${s}</b>` : '') + `<span>${t}</span>`; c.style.opacity = 1; }""",
        [step, text, gold],
    )


async def card(page: Page, title: str, sub: str, hold_ms: int) -> None:
    await page.evaluate(OVERLAY_JS)
    await page.evaluate(
        """([h, p]) => { const d = document.createElement('div'); d.id = 'demo-card';
             d.innerHTML = `<div class="cl"><span style="left:26px;top:0;background:#000"></span>
               <span style="left:0;top:38px;background:#DD0000;opacity:.88"></span>
               <span style="left:52px;top:38px;background:#FFCC00;opacity:.88"></span></div><h1>${h}</h1><p>${p}</p>`;
             document.body.appendChild(d); }""",
        [title, sub],
    )
    await page.wait_for_timeout(hold_ms)


async def remove_card(page: Page) -> None:
    await page.evaluate("() => { const d = document.getElementById('demo-card'); if (d) { d.style.opacity = 0; setTimeout(() => d.remove(), 520); } }")
    await page.wait_for_timeout(600)


async def scroll_to(page: Page, selector: str) -> None:
    await page.evaluate("(s) => document.querySelector(s).scrollIntoView({behavior: 'smooth', block: 'center'})", selector)
    await page.wait_for_timeout(1100)


async def click(page: Page, locator, pause: int = 350) -> None:
    box = await locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.evaluate("([x, y]) => { const c = document.getElementById('demo-cursor'); c.style.left = x + 'px'; c.style.top = y + 'px'; }", [x, y])
    await page.wait_for_timeout(750)
    await page.evaluate("() => { const c = document.getElementById('demo-cursor'); c.style.transform = 'scale(.7)'; setTimeout(() => c.style.transform = '', 160); }")
    await locator.click()
    await page.wait_for_timeout(pause)


async def type_into(page: Page, locator, text: str, delay: int = 38) -> None:
    await click(page, locator, 150)
    await locator.fill("")
    await page.keyboard.type(text, delay=delay)


async def record(video_dir: Path) -> Path:
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None)
        ctx = await browser.new_context(viewport=SIZE, record_video_dir=str(video_dir), record_video_size=SIZE, locale="de-DE")
        page = await ctx.new_page()
        await page.route(BOOKING_URL + "**", lambda route: route.fulfill(content_type="text/html; charset=utf-8",
                                                                        body=PLACEHOLDER.format(url=BOOKING_URL)))
        await page.goto(WEB)
        await page.wait_for_load_state("networkidle")
        await card(page, "Termin beim Amt.", "Von der Frage im Chat bis zur amtlichen Buchungsseite – aufgenommen in der echten App, ohne Sprachmodell.", 3200)
        await scroll_to(page, "#assistant-chat")
        await remove_card(page)

        chat = page.locator(".agent-card", has=page.locator("h3", has_text="Mit dem Assistenten schreiben"))
        await caption(page, "1", "Wunsch im Chat äußern")
        await type_into(page, chat.locator("input"), "Buche mir einen Termin beim Bürgeramt Berlin für einen neuen Personalausweis")
        await click(page, chat.locator("button[type=submit]"))
        action = chat.locator(".chat-action")
        await action.wait_for()
        await page.wait_for_timeout(2600)

        await caption(page, "2", "Vorschlag übernehmen – das Anliegen ist schon ausgefüllt")
        await click(page, action, 1300)
        termin = page.locator(".agent-card", has=page.locator("h3", has_text="Termin vorbereiten"))
        inputs = termin.locator("form input")
        await type_into(page, inputs.nth(1), "Berlin")
        await page.wait_for_timeout(700)

        await caption(page, "3", "Nur amtliche Buchungsseiten – fremde Adressen werden abgelehnt", gold=True)
        await type_into(page, inputs.nth(2), "https://termine-sofort.example/berlin", delay=28)
        await click(page, termin.locator("button[type=submit]"))
        await termin.locator(".error").wait_for()
        await page.wait_for_timeout(3400)
        await type_into(page, inputs.nth(2), BOOKING_URL, delay=30)
        await click(page, termin.locator("button[type=submit]"), 900)

        await caption(page, "4", "Vorschau prüfen und bestätigen")
        await scroll_to(page, ".action-preview")
        await page.wait_for_timeout(1500)
        await click(page, termin.locator("button", has_text="Bestätigen"), 600)
        link = termin.locator("a.button")
        await link.wait_for()
        await page.wait_for_timeout(2800)

        await caption(page, "5", "Gebucht wird auf der amtlichen Seite – von Ihnen selbst")
        await link.evaluate("a => a.removeAttribute('target')")  # im selben Tab öffnen, damit es im Video bleibt
        await click(page, link, 0)
        await page.wait_for_load_state("load")
        await caption(page, "5", "Gebucht wird auf der amtlichen Seite – von Ihnen selbst")
        await page.evaluate("() => document.getElementById('demo-cursor').style.display = 'none'")
        await page.wait_for_timeout(3600)
        await card(page, "Vorbereiten. Bestätigen. Selbst buchen.",
                   "Automatisch gebucht wird nicht: Viele Terminportale schützen sich mit Captcha oder BundID-Anmeldung.", 3800)

        video = await page.video.path()
        await ctx.close()
        await browser.close()
        return Path(video)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required")
    with tempfile.TemporaryDirectory() as tmp:
        webm = asyncio.run(record(Path(tmp)))
        ffmpeg("-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow",
               "-movflags", "+faststart", "-an", str(OUT / f"{NAME}.mp4"))
        palette = str(Path(tmp) / "palette.png")
        ffmpeg("-i", str(webm), "-vf", "fps=10,scale=860:-1:flags=lanczos,palettegen=max_colors=64:stats_mode=diff", palette)
        ffmpeg("-i", str(webm), "-i", palette, "-lavfi",
               "fps=10,scale=860:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=none:diff_mode=rectangle",
               str(OUT / f"{NAME}.gif"))
    print("wrote", OUT / f"{NAME}.mp4", "and", OUT / f"{NAME}.gif")


if __name__ == "__main__":
    main()
