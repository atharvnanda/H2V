"""
core/ffmpeg_runner.py
Generic FFmpeg executor — accepts a pre-built command list, streams stderr
live to the terminal, and raises a clear RuntimeError on failure.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Sequence


def run(cmd: Sequence[str]) -> None:
    """Execute *cmd* via subprocess, streaming FFmpeg output to the terminal.

    FFmpeg writes all its progress/diagnostics to stderr, so we pipe that
    and echo it line-by-line.  stdout is left untouched (FFmpeg rarely uses
    it when writing to a file).

    Raises
    ------
    RuntimeError
        If FFmpeg exits with a non-zero return code.
    """
    process = subprocess.Popen(
        list(cmd),
        stdout=sys.stdout,   # pass through; FFmpeg won't write here for file output
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,           # line-buffered
    )

    stderr_lines: list[str] = []
    assert process.stderr is not None  # guaranteed by stderr=PIPE

    for line in process.stderr:
        print(line, end="", file=sys.stderr)
        stderr_lines.append(line)

    process.wait()

    if process.returncode != 0:
        stderr_tail = "".join(stderr_lines[-30:])  # last 30 lines for context
        raise RuntimeError(
            f"FFmpeg exited with code {process.returncode}.\n\n"
            f"--- FFmpeg stderr (last 30 lines) ---\n{stderr_tail}"
        )
