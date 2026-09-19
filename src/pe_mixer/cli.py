"""CLI-Schnittstelle für den Auto-Mixer."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pe_mixer.analysis.analyzer import analyze_tracks
from pe_mixer.config import load_setup, validate_and_match_tracks
from pe_mixer.mix.planner import generate_mix_plan
from pe_mixer.mix.renderer import render_mix

app = typer.Typer(help="PE Audio-Mixer: Automatischer Proben-Grobmix aus FLAC-Multitrack-Spuren.")
console = Console()


@app.command()
def analyze(
    input_dir: Path = typer.Argument(
        ...,
        help="Pfad zum Ordner mit den FLAC-Aufnahmen",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    setup: str = typer.Option(
        "probe",
        "--setup",
        "-s",
        help="Name des Setups (z. B. 'probe' für setups/probe.yml)",
    ),
):
    """Analysiert die Audiospuren und gibt Pegel, Lautheit (LUFS) und Frequenzen aus."""
    console.print(
        Panel(
            f"[bold cyan]Audio-Analyse für:[/bold cyan] {input_dir}\n[bold cyan]Setup:[/bold cyan] {setup}",
            title="PE Audio-Mixer",
        )
    )

    try:
        setup_cfg = load_setup(setup)
    except Exception as e:
        console.print(f"[bold red]Fehler beim Laden des Setups:[/bold red] {e}")
        raise typer.Exit(code=1)

    matched, missing, unknown = validate_and_match_tracks(input_dir, setup_cfg)

    # Validierungs-Warnungen
    if missing:
        console.print(
            f"[yellow]Warnung: {len(missing)} Spur(en) aus dem Setup fehlen im Verzeichnis:[/yellow]"
        )
        for m in missing:
            console.print(f"  [red]✗[/red] {m}")

    if unknown:
        console.print(
            f"[dim]Hinweis: {len(unknown)} unbekannte Spur(en) gefunden (nicht gemischt):[/dim]"
        )
        for u in unknown:
            console.print(f"  [dim]?[/dim] {u}")

    if not matched:
        console.print("[bold red]Keine passenden Spuren zum Analysieren gefunden![/bold red]")
        raise typer.Exit(code=1)

    console.print("\n[bold]Analysiere Spuren...[/bold]")
    analyses = analyze_tracks(matched, setup_cfg)

    table = Table(title="Spur-Analysen")
    table.add_column("Datei", style="cyan")
    table.add_column("Instrument", style="green")
    table.add_column("Gruppe", style="magenta")
    table.add_column("Dauer", justify="right")
    table.add_column("Peak (dBFS)", justify="right")
    table.add_column("RMS (dBFS)", justify="right")
    table.add_column("LUFS", justify="right")
    table.add_column("Dynamik (dB)", justify="right")

    for filename, a in analyses.items():
        peak_str = f"{a.peak_db:.1f}" if not a.is_silent else "-∞"
        rms_str = f"{a.rms_db:.1f}" if not a.is_silent else "-∞"
        lufs_str = f"{a.lufs:.1f}" if not a.is_silent else "-∞"
        table.add_row(
            filename,
            a.instrument,
            a.group,
            f"{a.duration_sec:.1f}s",
            peak_str,
            rms_str,
            lufs_str,
            f"{a.crest_factor_db:.1f}",
        )

    console.print(table)


@app.command()
def mix(
    input_dir: Path = typer.Argument(
        ...,
        help="Pfad zum Ordner mit den FLAC-Aufnahmen",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    setup: str = typer.Option(
        "probe",
        "--setup",
        "-s",
        help="Name des Setups (z. B. 'probe' für setups/probe.yml)",
    ),
    output_dir: Path = typer.Option(
        Path("./output"),
        "--output",
        "-o",
        help="Zielordner für die Ausgabedateien (mix.mp3, mix.flac, mix.json)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Dateiname für den Mix (Standard: Name des Eingabe-Ordners)",
    ),
):
    """Erzeugt automatisch einen sauberen Grobmix aus den Einzelspuren."""
    base_name = name or input_dir.name
    console.print(
        Panel(
            f"[bold green]Starte Proben-Grobmix[/bold green]\n"
            f"[bold]Eingabe:[/bold] {input_dir}\n"
            f"[bold]Setup:[/bold]   {setup}\n"
            f"[bold]Ausgabe:[/bold] {output_dir} ({base_name}.*)\n",
            title="PE Audio-Mixer",
        )
    )

    try:
        setup_cfg = load_setup(setup)
    except Exception as e:
        console.print(f"[bold red]Fehler beim Laden des Setups:[/bold red] {e}")
        raise typer.Exit(code=1)

    matched, missing, unknown = validate_and_match_tracks(input_dir, setup_cfg)

    if missing:
        console.print(f"[yellow]Achtung: {len(missing)} Spur(en) fehlen im Verzeichnis:[/yellow]")
        for m in missing:
            console.print(f"  [red]✗[/red] {m}")

    if unknown:
        console.print(f"[dim]Hinweis: {len(unknown)} Spur(en) nicht im Setup zugeordnet.[/dim]")

    if not matched:
        console.print("[bold red]Keine passenden Spuren zum Mischen gefunden![/bold red]")
        raise typer.Exit(code=1)

    # 1. Analyse
    console.print(f"\n[bold]1. Analysiere {len(matched)} Spuren...[/bold]")
    analyses = analyze_tracks(matched, setup_cfg)

    # 2. Heuristischer Mixplan
    console.print("[bold]2. Berechne Mixplan...[/bold]")
    plan = generate_mix_plan(analyses, setup_cfg)

    plan_table = Table(title="Mixplan (Kanalzüge)")
    plan_table.add_column("Spur", style="cyan")
    plan_table.add_column("Instrument", style="green")
    plan_table.add_column("Gain (dB)", justify="right", style="bold yellow")
    plan_table.add_column("Pan", justify="right")
    plan_table.add_column("Highpass", justify="right")

    for filename, p in plan.tracks.items():
        pan_str = (
            "Center"
            if abs(p.pan) < 0.05
            else (f"L {abs(p.pan):.2f}" if p.pan < 0 else f"R {p.pan:.2f}")
        )
        hp_str = f"{int(p.highpass_hz)} Hz" if p.highpass_hz else "Aus"
        plan_table.add_row(
            filename,
            p.instrument,
            f"{p.gain_db:+.1f} dB",
            pan_str,
            hp_str,
        )

    console.print(plan_table)

    # 3. DSP & Rendering
    console.print("\n[bold]3. Rendere Mix & wende Master-Limiter an...[/bold]")
    output_files = render_mix(matched, plan, output_dir, base_name=base_name)

    # Analyse als JSON mitspeichern
    analysis_json_path = output_dir / f"{base_name}_analysis.json"
    with open(analysis_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {k: v.to_dict() for k, v in analyses.items()},
            f,
            indent=2,
            ensure_ascii=False,
        )

    console.print("\n[bold green]✓ Mix erfolgreich fertiggestellt![/bold green]")
    for fmt, path in output_files.items():
        console.print(f"  [bold]• {fmt.upper()}:[/bold] {path}")
    console.print(f"  [bold]• ANALYSIS:[/bold] {analysis_json_path}")


if __name__ == "__main__":
    app()
