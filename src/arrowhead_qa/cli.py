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
    input_csv: Path = typer.Argument(..., help="CSV file with columns: url, customer_name, customer_number"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    min_severity: Optional[str] = typer.Option(None, "--min-severity"),
    csv_out: Optional[Path] = typer.Option(
        Path("reports/summary.csv"), "--csv", help="Write per-call flag summary CSV here"
    ),
):
    """Analyze many calls from a CSV (columns: url, customer_name, customer_number)."""
    import csv

    cfg = _apply_overrides(load_config(config), model, min_severity, None)

    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Normalise header names: strip whitespace, lowercase
        rows_in = []
        for row in reader:
            rows_in.append({k.strip().lower(): v.strip() for k, v in row.items()})

    if not rows_in:
        console.print("[red]CSV is empty.[/red]")
        raise typer.Exit(2)

    required = {"url"}
    missing = required - set(rows_in[0].keys())
    if missing:
        console.print(f"[red]CSV missing required column(s): {missing}. Headers found: {list(rows_in[0].keys())}[/red]")
        raise typer.Exit(2)

    console.print(f"[bold]Processing {len(rows_in)} calls…[/bold]")

    out_rows = []
    for i, row in enumerate(rows_in, 1):
        src = row["url"]
        name = row.get("customer_name", "")
        number = row.get("customer_number", "")
        label = f"{name} ({number})" if name or number else src
        console.print(f"\n[bold cyan]({i}/{len(rows_in)}) {label}[/bold cyan]")
        try:
            result = analyze_audio(src, cfg)
            render(result, cfg, f"{label} — {src}")
            save(result, cfg, src)
            if result.flags:
                for fl in result.flags:
                    out_rows.append({
                        "customer_name": name,
                        "customer_number": number,
                        "url": src,
                        "overall_severity": result.overall_severity,
                        "call_summary": result.call_summary,
                        "flag_category": fl.category,
                        "flag_severity": fl.severity,
                        "timestamp": fl.timestamp or "",
                        "speaker": fl.speaker,
                        "quote": fl.quote,
                        "explanation": fl.explanation,
                        "recommendation": fl.recommendation,
                    })
            else:
                out_rows.append({
                    "customer_name": name,
                    "customer_number": number,
                    "url": src,
                    "overall_severity": result.overall_severity,
                    "call_summary": result.call_summary,
                    "flag_category": "",
                    "flag_severity": "",
                    "timestamp": "",
                    "speaker": "",
                    "quote": "",
                    "explanation": "",
                    "recommendation": "",
                })
        except Exception as e:
            console.print(f"[red]failed: {e}[/red]")
            out_rows.append({
                "customer_name": name,
                "customer_number": number,
                "url": src,
                "overall_severity": "error",
                "call_summary": str(e),
                "flag_category": "_error",
                "flag_severity": "critical",
                "timestamp": "", "speaker": "", "quote": "", "explanation": str(e), "recommendation": "",
            })

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "customer_name", "customer_number", "url",
        "overall_severity", "call_summary",
        "flag_category", "flag_severity", "timestamp", "speaker",
        "quote", "explanation", "recommendation",
    ]
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    console.print(f"[green]Summary CSV → {csv_out}[/green] ({len(out_rows)} rows)")


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
