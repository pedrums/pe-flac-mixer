# pe-flac-mixer

Automatic rough mix generator for band rehearsals and live recordings from FLAC multitrack files.

> **Documentation:** For full guides, usage instructions, configuration, and API references, please visit the [pe-flac-mixer Documentation](https://pedrums.github.io/pe-flac-mixer/).

## Installation

Ensure [uv](https://github.com/astral-sh/uv) and [FFmpeg](https://ffmpeg.org/) are installed.

You can install the tool globally or run it directly from source/git via `uv`:

```bash
# Clone and install as tool locally
uv tool install .

# Or run directly via uvx / uv run from anywhere
uvx pe-flac-mixer --help
```

## Usage

When you are inside your rehearsal or multi-track session folder (containing song subdirectories), you can run bulk mixing directly without specifying arguments (defaults to current directory `.`):

```bash
# Bulk mix all subdirectories in current folder
pe-flac-mixer mix --bulk --setup probe

# Or single mix in current folder
pe-flac-mixer mix . --setup probe

# Cut X seconds from the beginning of an MP3 file
pe-flac-mixer cut song.mp3 --sec 3
```
