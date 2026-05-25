"""Core analyzers: audio + dashboard text."""
from __future__ import annotations
from pathlib import Path
from rich.console import Console

from .config import Config
from .gemini import get_client, download_to_tempfile, upload_and_wait, call_gemini_json
from .prompts import build_system_prompt, build_audio_user_prompt, build_text_user_prompt
from .schema import AnalysisResult

console = Console()


def analyze_audio(source: str, cfg: Config) -> AnalysisResult:
    """source: URL (http/https) or local file path."""
    client = get_client()
    cleanup = False
    if source.startswith("http://") or source.startswith("https://"):
        console.print(f"[dim]downloading audio…[/dim]")
        path = download_to_tempfile(source)
        cleanup = True
    else:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)

    try:
        size_mb = path.stat().st_size / 1e6
        console.print(f"[dim]uploading {size_mb:.2f} MB to Gemini Files API…[/dim]")
        uploaded = upload_and_wait(client, path)
        sys_prompt = build_system_prompt(cfg)
        user_prompt = build_audio_user_prompt(cfg, source)
        console.print(f"[dim]analyzing with {cfg.model.name}…[/dim]")
        return call_gemini_json(client, cfg, [uploaded, user_prompt], sys_prompt)
    finally:
        if cleanup:
            try:
                path.unlink()
            except OSError:
                pass


def analyze_text(source: str, transcript: str, cfg: Config) -> AnalysisResult:
    client = get_client()
    sys_prompt = build_system_prompt(cfg)
    user_prompt = build_text_user_prompt(cfg, source, transcript)
    return call_gemini_json(client, cfg, [user_prompt], sys_prompt)
