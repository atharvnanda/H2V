"""
main.py — H2V CLI entry point

Usage
─────
  python main.py --input path/to/video.mp4
  python main.py -i video.mp4 -o output/custom_name.mp4 --template breaking_news_2_panels

The constructed FFmpeg command is printed to the terminal before execution
so you can verify or copy-paste it for manual debugging.
"""
from __future__ import annotations

import argparse
import importlib
import shlex
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="h2v",
        description="Convert a 16:9 news video to 9:16 vertical format using FFmpeg.",
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        metavar="INPUT",
        help="Path to the source 16:9 video file.",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="OUTPUT",
        help=(
            "Path for the output 9:16 video. "
            "Defaults to output/<input_stem>_vertical.mp4"
        ),
    )
    parser.add_argument(
        "-t", "--template",
        default="breaking_news_2_panels",
        metavar="TEMPLATE",
        help=(
            "Template name to use for layout (must match a folder under templates/). "
            "Default: breaking_news_2_panels"
        ),
    )
    return parser.parse_args()


def resolve_output_path(input_path: Path, output_arg: str | None) -> Path:
    """Return an absolute output path, creating the output/ dir if needed."""
    if output_arg:
        out = Path(output_arg).resolve()
    else:
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        out = output_dir / f"{input_path.stem}_vertical.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def load_transformer(template_name: str):
    """Dynamically import and return the transformer module for *template_name*.

    Expects the module at: templates.<template_name>.transformer
    That module must expose a build_command(input_path, output_path) function.
    """
    module_path = f"templates.{template_name}.transformer"
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError:
        available = [
            p.name
            for p in (Path(__file__).parent / "templates").iterdir()
            if p.is_dir() and not p.name.startswith("_")
        ]
        print(
            f"[ERROR] Template '{template_name}' not found.\n"
            f"        Available templates: {', '.join(available) or 'none'}",
            file=sys.stderr,
        )
        sys.exit(1)


def print_command(cmd: list[str]) -> None:
    """Pretty-print the FFmpeg command so it can be inspected or copy-pasted."""
    print("\n" + "─" * 60)
    print("FFmpeg command to be executed:")
    print("─" * 60)
    # shlex.join gives a shell-safe, copy-pasteable representation
    print(shlex.join(cmd))
    print("─" * 60 + "\n")


def main() -> None:
    args = parse_args()

    input_path  = Path(args.input).resolve()
    output_path = resolve_output_path(input_path, args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    transformer = load_transformer(args.template)

    print(f"[h2v] Template  : {args.template}")
    print(f"[h2v] Input     : {input_path}")
    print(f"[h2v] Output    : {output_path}")

    cmd = transformer.build_command(str(input_path), str(output_path))

    print_command(cmd)

    # Lazy import so the rest of the CLI is usable even without ffmpeg installed
    from core import ffmpeg_runner

    try:
        ffmpeg_runner.run(cmd)
        print(f"\n[h2v] ✓ Done. Output saved to: {output_path}")
    except RuntimeError as exc:
        print(f"\n[h2v] ✗ FFmpeg failed:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
