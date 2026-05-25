"""Optional fallback: scrape transcript from Arrowhead dashboard via Playwright."""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from rich.console import Console

console = Console()


def scrape_transcript(url: str, profile_dir: Path, wait_ms: int = 60_000) -> str:
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PWTimeout:
            pass

        console.print("[dim]waiting up to 60s for transcript pane (log in if prompted)…[/dim]")
        text = ""
        deadline = page.evaluate("() => Date.now()") + wait_ms
        while True:
            try:
                body = page.inner_text("body", timeout=2000)
            except Exception:
                body = ""
            if (
                any(m in body.lower() for m in ["bot:", "customer:", "agent:", "assistant:"])
                and len(body) > 400
            ):
                text = body
                break
            if page.evaluate("() => Date.now()") > deadline:
                text = body
                break
            page.wait_for_timeout(1500)

        # Try to narrow.
        for sel in [
            '[data-testid*="transcript" i]',
            '[class*="transcript" i]',
            '[id*="transcript" i]',
            "main",
        ]:
            try:
                el = page.query_selector(sel)
                if el:
                    t = el.inner_text()
                    if (
                        any(m in t.lower() for m in ["bot:", "customer:", "agent:", "assistant:"])
                        and len(t) > 200
                    ):
                        text = t
                        break
            except Exception:
                continue

        ctx.close()
        return text
