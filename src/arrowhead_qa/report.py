"""Render report to terminal + write JSON/Markdown files."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Config
from .schema import AnalysisResult

console = Console()
SEV_COLOR = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "cyan", "none": "green"}
SEV_ORDER = ["none", "low", "medium", "high", "critical"]


def render(result: AnalysisResult, cfg: Config, source: str) -> None:
    console.print(Panel.fit(
        f"[bold]Arrowhead Call QA[/bold]\nSource: {source}\nModel: {cfg.model.name}",
        border_style="blue",
    ))

    sev = result.overall_severity
    console.print(f"\n[bold]Summary:[/bold] {result.call_summary}")
    console.print(f"[bold]Overall severity:[/bold] [{SEV_COLOR.get(sev, 'white')}]{sev}[/]")

    m = result.metrics
    mt = Table(title="Metrics", show_header=False, border_style="dim")
    for k, v in m.model_dump().items():
        mt.add_row(k, str(v))
    console.print(mt)

    lq = result.language_quality
    console.print(
        f"[bold]Language:[/bold] bot={lq.bot_language} | customer={lq.customer_language}"
    )
    if lq.code_switching_issues:
        console.print(f"  [dim]{lq.code_switching_issues}[/dim]")

    visible = result.severity_at_or_above(cfg.analysis.min_severity)  # type: ignore[arg-type]
    if not visible:
        console.print("\n[green]No flags at or above threshold.[/green]")
        return

    t = Table(title=f"Flags ({len(visible)} / {len(result.flags)} total)", border_style="dim")
    t.add_column("#", style="dim", width=3)
    t.add_column("Sev")
    t.add_column("Time", width=8)
    t.add_column("Speaker", width=8)
    t.add_column("Category")
    t.add_column("Quote", overflow="fold")
    t.add_column("Why", overflow="fold")
    t.add_column("Fix", overflow="fold")
    for i, f in enumerate(visible, 1):
        t.add_row(
            str(i),
            f"[{SEV_COLOR.get(f.severity, 'white')}]{f.severity}[/]",
            f.timestamp or "",
            f.speaker,
            f.category,
            (f.quote or "")[:160],
            f.explanation,
            f.recommendation,
        )
    console.print(t)


def save(result: AnalysisResult, cfg: Config, source: str) -> dict[str, Path]:
    out = {}
    reports_dir = Path(cfg.output.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = reports_dir / f"report-{stamp}"

    if cfg.output.save_json:
        p = base.with_suffix(".json")
        p.write_text(json.dumps({
            "source": source,
            "model": cfg.model.name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            **result.model_dump(),
        }, indent=2, ensure_ascii=False))
        out["json"] = p

    if cfg.output.save_markdown:
        p = base.with_suffix(".md")
        p.write_text(_to_markdown(result, source, cfg))
        out["markdown"] = p

    return out


def _to_markdown(r: AnalysisResult, source: str, cfg: Config) -> str:
    lines = [
        f"# Arrowhead Call QA Report",
        f"",
        f"- **Source:** {source}",
        f"- **Model:** {cfg.model.name}",
        f"- **Generated:** {datetime.utcnow().isoformat()}Z",
        f"- **Overall severity:** `{r.overall_severity}`",
        f"",
        f"## Summary",
        r.call_summary or "_(none)_",
        f"",
        f"## Metrics",
    ]
    for k, v in r.metrics.model_dump().items():
        lines.append(f"- **{k}:** {v}")
    lines += [
        "",
        f"## Language",
        f"- bot: `{r.language_quality.bot_language}`",
        f"- customer: `{r.language_quality.customer_language}`",
        f"- notes: {r.language_quality.code_switching_issues or '_(none)_'}",
        "",
        f"## Flags ({len(r.flags)})",
        "",
    ]
    for i, f in enumerate(r.flags, 1):
        lines += [
            f"### {i}. `{f.category}` — {f.severity}",
            f"- **time:** {f.timestamp or 'n/a'} | **speaker:** {f.speaker} | **turn:** {f.turn_index}",
            f"- **quote:** {f.quote}",
            f"- **why:** {f.explanation}",
            f"- **fix:** {f.recommendation}",
            "",
        ]
    if r.transcript:
        lines += ["## Transcript", "", "```", r.transcript, "```"]
    return "\n".join(lines)
