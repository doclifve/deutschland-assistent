"""Render the keynote-style walkthrough (docs/media/<NAME>.mp4 and .gif).

The film is driven frame by frame through window.render(t), so motion is exact
regardless of machine speed. It reuses the web app's stylesheet, so re-run this
after UI changes.

Requirements: Python with `playwright` (plus `playwright install chromium`) and ffmpeg.

    python docs/media/rundgang/render.py
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
FPS = 30
# Bump the version whenever the film changes: GitHub and browsers cache images by
# file name, so a re-render under the same name keeps showing the old animation.
NAME = "rundgang-v2"


async def render_frames(frames: Path) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto((HERE / "film.html").as_uri())
        await page.wait_for_timeout(300)
        total = int(await page.evaluate("DURATION") * FPS)
        for i in range(total):
            await page.evaluate(f"render({i / FPS})")
            await page.screenshot(path=str(frames / f"f{i:04d}.jpg"), type="jpeg", quality=95)
        await browser.close()


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required")
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp)
        asyncio.run(render_frames(frames))
        pattern = str(frames / "f%04d.jpg")
        ffmpeg("-framerate", str(FPS), "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-crf", "18", "-preset", "slow", "-movflags", "+faststart", str(OUT / f"{NAME}.mp4"))
        palette = str(frames / "palette.png")
        ffmpeg("-framerate", str(FPS), "-i", pattern, "-vf",
               "fps=15,scale=960:-1:flags=lanczos,palettegen=max_colors=128:stats_mode=diff", palette)
        ffmpeg("-framerate", str(FPS), "-i", pattern, "-i", palette, "-lavfi",
               "fps=15,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a:diff_mode=rectangle",
               str(OUT / f"{NAME}.gif"))
    print("wrote", OUT / f"{NAME}.mp4", "and", OUT / f"{NAME}.gif", "- update the README if NAME changed")


if __name__ == "__main__":
    main()
