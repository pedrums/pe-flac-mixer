"""CLI interface for pe-flac-mixer."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pe_flac_mixer.analysis.analyzer import analyze_tracks
from pe_flac_mixer.config import load_setup, normalize_path, validate_and_match_tracks
from pe_flac_mixer.generator import generate_setup_from_directory, save_setup_file
from pe_flac_mixer.mix.planner import generate_mix_plan
from pe_flac_mixer.mix.renderer import render_mix

app = typer.Typer(help="pe-flac-mixer: Automatic rough mix from FLAC multitrack stems.")
console = Console()


@app.command()
def analyze(
    input_dir: str = typer.Argument(
        ...,
        help="Path to folder containing multitrack FLAC recordings (supports Windows & Linux paths)",
    ),
    setup: str = typer.Option(
        "probe",
        "--setup",
        "-s",
        help="Name of the setup (e.g. 'probe' for setups/probe.yml)",
    ),
):
    """Analyze audio tracks and display peak levels, loudness (LUFS), and crest factor."""
    dir_path = normalize_path(input_dir)
    if not dir_path or not dir_path.is_dir():
        console.print(
            f"[bold red]Error: Directory does not exist:[/bold red] {dir_path or input_dir}"
        )
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold cyan]Audio analysis for:[/bold cyan] {dir_path}\n[bold cyan]Setup:[/bold cyan] {setup}",
            title="pe-flac-mixer",
        )
    )

    try:
        setup_cfg = load_setup(setup)
    except Exception as e:
        console.print(f"[bold red]Error loading setup:[/bold red] {e}")
        raise typer.Exit(code=1)

    matched, missing, unknown = validate_and_match_tracks(dir_path, setup_cfg)

    # Validation warnings
    if missing:
        console.print(
            f"[yellow]Warning: {len(missing)} track(s) from setup not found in directory:[/yellow]"
        )
        for m in missing:
            console.print(f"  [red]✗[/red] {m}")

    if unknown:
        console.print(
            f"[dim]Notice: {len(unknown)} unknown track(s) found (will not be mixed):[/dim]"
        )
        for u in unknown:
            console.print(f"  [dim]?[/dim] {u}")

    if not matched:
        console.print("[bold red]No matching tracks found to analyze![/bold red]")
        raise typer.Exit(code=1)

    console.print("\n[bold]Analyzing tracks...[/bold]")
    analyses = analyze_tracks(matched, setup_cfg)

    table = Table(title="Track Analysis")
    table.add_column("File", style="cyan")
    table.add_column("Instrument", style="green")
    table.add_column("Group", style="magenta")
    table.add_column("Duration", justify="right")
    table.add_column("Peak (dBFS)", justify="right")
    table.add_column("RMS (dBFS)", justify="right")
    table.add_column("LUFS", justify="right")
    table.add_column("Dynamic (dB)", justify="right")

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
    input_dir: str = typer.Argument(
        ...,
        help="Path to folder containing multitrack FLAC recordings (supports Windows & Linux paths)",
    ),
    setup: str = typer.Option(
        "probe",
        "--setup",
        "-s",
        help="Name of the setup (e.g. 'probe' for setups/probe.yml)",
    ),
    output_dir: str = typer.Option(
        "./output",
        "--output",
        "-o",
        help="Target folder for rendered outputs (mix.mp3, mix.flac, mix.json)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Base file name for the mix (defaults to name of input directory)",
    ),
):
    """Automatically generates a clean rough mix from multitrack stems."""
    in_dir = normalize_path(input_dir)
    if not in_dir or not in_dir.is_dir():
        console.print(
            f"[bold red]Error: Directory does not exist:[/bold red] {in_dir or input_dir}"
        )
        raise typer.Exit(code=1)

    out_dir = normalize_path(output_dir) or Path("./output")
    base_name = name or in_dir.name
    console.print(
        Panel(
            f"[bold green]Starting Rough Mix[/bold green]\n"
            f"[bold]Input:[/bold]  {in_dir}\n"
            f"[bold]Setup:[/bold]  {setup}\n"
            f"[bold]Output:[/bold] {out_dir} ({base_name}.*)\n",
            title="pe-flac-mixer",
        )
    )

    try:
        setup_cfg = load_setup(setup)
    except Exception as e:
        console.print(f"[bold red]Error loading setup:[/bold red] {e}")
        raise typer.Exit(code=1)

    matched, missing, unknown = validate_and_match_tracks(in_dir, setup_cfg)

    if missing:
        console.print(f"[yellow]Warning: {len(missing)} track(s) missing from directory:[/yellow]")
        for m in missing:
            console.print(f"  [red]✗[/red] {m}")

    if unknown:
        console.print(f"[dim]Notice: {len(unknown)} unmapped track(s) found.[/dim]")

    if not matched:
        console.print("[bold red]No matching tracks found to mix![/bold red]")
        raise typer.Exit(code=1)

    # 1. Analysis
    console.print(f"\n[bold]1. Analyzing {len(matched)} tracks...[/bold]")
    analyses = analyze_tracks(matched, setup_cfg)

    # 2. Heuristic Mix Plan
    console.print("[bold]2. Calculating mix plan...[/bold]")
    plan = generate_mix_plan(analyses, setup_cfg)

    plan_table = Table(title="Mix Plan (Channel Strips)")
    plan_table.add_column("Track", style="cyan")
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
        hp_str = f"{int(p.highpass_hz)} Hz" if p.highpass_hz else "Off"
        plan_table.add_row(
            filename,
            p.instrument,
            f"{p.gain_db:+.1f} dB",
            pan_str,
            hp_str,
        )

    console.print(plan_table)

    # 3. DSP & Rendering
    console.print("\n[bold]3. Rendering mix & applying master limiter...[/bold]")
    output_files = render_mix(matched, plan, output_dir, base_name=base_name)

    # Save analysis as JSON alongside mix
    analysis_json_path = output_dir / f"{base_name}_analysis.json"
    with open(analysis_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {k: v.to_dict() for k, v in analyses.items()},
            f,
            indent=2,
            ensure_ascii=False,
        )

    console.print("\n[bold green]✓ Mix finished successfully![/bold green]")
    for fmt, path in output_files.items():
        console.print(f"  [bold]• {fmt.upper()}:[/bold] {path}")
    console.print(f"  [bold]• ANALYSIS:[/bold] {analysis_json_path}")


@app.command(name="create-setup")
def create_setup(
    input_dir: str | None = typer.Argument(
        None,
        help="Path to directory containing FLAC recordings (optional if --source is used)",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Path to directory containing FLAC recordings (supports Windows & Linux paths)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Name of the setup (defaults to source folder name)",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Target YAML file path (defaults to setups/<name>.yml)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite target YAML file if it already exists",
    ),
):
    """Generates a setup YAML file by automatically guessing instruments and channel routing from FLAC files."""
    raw_src = source or input_dir
    if not raw_src:
        console.print(
            "[bold red]Error: Please specify the source directory either as argument or via '--source / -s'.[/bold red]"
        )
        raise typer.Exit(code=1)

    src_dir = normalize_path(raw_src)
    if not src_dir or not src_dir.is_dir():
        console.print(
            f"[bold red]Error: Source directory does not exist: {src_dir or raw_src}[/bold red]"
        )
        raise typer.Exit(code=1)

    setup_name = name or src_dir.name
    target_path = normalize_path(output) if output else (Path("setups") / f"{setup_name}.yml")

    console.print(
        Panel(
            f"[bold green]Auto-Generating Setup[/bold green]\n"
            f"[bold]Source directory:[/bold] {src_dir}\n"
            f"[bold]Setup name:[/bold]       {setup_name}\n"
            f"[bold]Target file:[/bold]      {target_path}",
            title="pe-flac-mixer",
        )
    )

    try:
        setup_cfg = generate_setup_from_directory(src_dir, setup_name=setup_name)
    except Exception as e:
        console.print(f"[bold red]Error inspecting directory:[/bold red] {e}")
        raise typer.Exit(code=1)

    try:
        saved_path = save_setup_file(setup_cfg, target_path, overwrite=force)
    except FileExistsError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Error saving setup file:[/bold red] {e}")
        raise typer.Exit(code=1)

    table = Table(title=f"Guessed Channels for Setup: [bold cyan]{setup_name}[/bold cyan]")
    table.add_column("File", style="cyan")
    table.add_column("Guessed Instrument", style="green")
    table.add_column("Group", style="magenta")
    table.add_column("Type", justify="center")
    table.add_column("Pan", justify="right")

    for filename, ch in setup_cfg.channels.items():
        pan_str = (
            "Center"
            if abs(ch.pan) < 0.05
            else (f"L {abs(ch.pan):.2f}" if ch.pan < 0 else f"R {ch.pan:.2f}")
        )
        table.add_row(filename, ch.name, ch.group, ch.type, pan_str)

    console.print(table)

    console.print(
        Panel(
            f"[bold yellow]⚠ Bitte kontrollieren! / Please review and verify:[/bold yellow]\n\n"
            f"Das Setup wurde erfolgreich generiert und abgelegt unter:\n"
            f"[bold cyan]{saved_path.resolve()}[/bold cyan]\n\n"
            f"Bitte kontrolliere vor dem Mischen insbesondere:\n"
            f"  1. [bold]Lead vs. Background Vocals[/bold] (Gruppe 'vocals lead' vs. 'vocals background')\n"
            f"  2. [bold]Panning[/bold] (Verteilung im Stereobild)\n"
            f"  3. Eventuelle [bold]Spezial-Instrumente[/bold] (z.B. Keys, Akustik-Gitarren)\n\n"
            f"Anschließend kannst du den Mix mit diesem Setup starten:\n"
            f'  [bold green]uv run pe-flac-mixer mix "{src_dir}" --setup "{setup_name}"[/bold green]',
            title="Setup Erstellt",
            border_style="yellow",
        )
    )


if __name__ == "__main__":
    app()
