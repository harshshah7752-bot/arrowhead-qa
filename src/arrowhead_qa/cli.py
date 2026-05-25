"""Typer CLI entry point."""
from __future__ import annotations
import json as _json
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from .config import load_config
from .analyze import analyze_audio, analyze_text
from .dashboard import scrape_transcript
from .report import render, save

load_dotenv()
console = Console()
app = typer.Typer(
    help="Arrowhead QA — Gemini-powered analyzer for AI voice-bot call recordings.",
    no_args_is_help=True,
    add_completion=False,
)


def _apply_overrides(cfg, model: Optional[str], min_severity: Optional[str], lang: Optional[str]):
    if model:
        cfg.model.name = model
    if min_severity:
        cfg.analysis.min_severity = min_severity
    if lang:
        cfg.analysis.expected_language = lang
    return cfg


@app.command()
def audio(
    source: str = typer.Argument(..., help="Audio URL (e.g. presigned S3) or local .wav/.mp3 path"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to user config YAML"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model (e.g. gemini-2.5-flash)"),
    min_severity: Optional[str] = typer.Option(None, "--min-severity", help="low|medium|high|critical"),
    lang: Optional[str] = typer.Option(None, "--lang", help="Expected language hint (auto|en|hi|hi-en)"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not write report files"),
):
    """Analyze a call audio recording."""
    cfg = _apply_overrides(load_config(config), model, min_severity, lang)
    if no_save:
        cfg.output.save_json = False
        cfg.output.save_markdown = False
    result = analyze_audio(source, cfg)
    render(result, cfg, source)
    paths = save(result, cfg, source) if (cfg.output.save_json or cfg.output.save_markdown) else {}
    for kind, p in paths.items():
        console.print(f"[dim]wrote {kind}: {p}[/dim]")


@app.command()
def dashboard(
    url: str = typer.Argument(..., help="dashboard-bot.arrowhead.team call URL"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    min_severity: Optional[str] = typer.Option(None, "--min-severity"),
    profile_dir: Path = typer.Option(Path(".playwright-profile"), help="Persistent browser profile dir"),
    no_save: bool = typer.Option(False, "--no-save"),
):
    """Scrape transcript from Arrowhead dashboard and analyze (fallback when audio unavailable)."""
    cfg = _apply_overrides(load_config(config), model, min_severity, None)
    if no_save:
        cfg.output.save_json = False
        cfg.output.save_markdown = False
    console.print("[bold]Opening dashboard — log in if prompted…[/bold]")
    transcript = scrape_transcript(url, profile_dir)
    if not transcript.strip():
        console.print("[red]Empty transcript. Aborting.[/red]")
        raise typer.Exit(2)
    result = analyze_text(url, transcript, cfg)
    render(result, cfg, url)
    paths = save(result, cfg, url) if (cfg.output.save_json or cfg.output.save_markdown) else {}
    for kind, p in paths.items():
        console.print(f"[dim]wrote {kind}: {p}[/dim]")


@app.command()
def batch(
    input_file: Path = typer.Argument(..., help="Text file with one audio URL or path per line"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    min_severity: Optional[str] = typer.Option(None, "--min-severity"),
    csv_out: Optional[Path] = typer.Option(None, "--csv", help="Write per-call flag CSV here"),
):
    """Analyze many audio files; emit one report per call and an optional CSV summary."""
    import csv
    cfg = _apply_overrides(load_config(config), model, min_severity, None)
    sources = [l.strip() for l in input_file.read_text().splitlines() if l.strip() and not l.startswith("#")]
    console.print(f"[bold]Processing {len(sources)} calls…[/bold]")

    rows = []
    for i, src in enumerate(sources, 1):
        console.print(f"\n[bold cyan]({i}/{len(sources)}) {src}[/bold cyan]")
        try:
            result = analyze_audio(src, cfg)
            render(result, cfg, src)
            save(result, cfg, src)
            for f in result.flags:
                rows.append({
                    "source": src,
                    "overall_severity": result.overall_severity,
                    "category": f.category,
                    "severity": f.severity,
                    "timestamp": f.timestamp or "",
                    "speaker": f.speaker,
                    "quote": f.quote,
                    "explanation": f.explanation,
                })
        except Exception as e:
            console.print(f"[red]failed: {e}[/red]")
            rows.append({"source": src, "category": "_error", "severity": "critical", "explanation": str(e)})

    if csv_out:
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["source", "overall_severity", "category", "severity", "timestamp", "speaker", "quote", "explanation"])
            w.writeheader()
            for r in rows:
                w.writerow(r)
        console.print(f"[green]CSV written: {csv_out}[/green]")


@app.command("init-config")
def init_config(
    path: Path = typer.Argument(Path("arrowhead-qa.yaml"), help="Where to write the starter config"),
):
    """Copy default.yaml to a local file you can edit."""
    from .config import DEFAULT_CONFIG
    if path.exists():
        console.print(f"[yellow]{path} already exists — aborting[/yellow]")
        raise typer.Exit(1)
    path.write_text(DEFAULT_CONFIG.read_text())
    console.print(f"[green]Wrote {path}. Edit and pass --config {path} (or it's auto-detected in cwd).[/green]")


@app.command("list-categories")
def list_categories(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Print active error categories."""
    cfg = load_config(config)
    for c in cfg.categories:
        status = "on" if c.enabled else "OFF"
        console.print(f"[{status}] {c.id} ({c.severity}) — {c.description}")


if __name__ == "__main__":
    app()
