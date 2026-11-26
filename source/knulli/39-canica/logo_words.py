#!/usr/bin/env python3
"""Draw the English console logos that are words (Extras and the utilities) into logos/, as the Spanish ones in
logos/es were drawn: white Roboto Black Italic, a small first line over a large second one, 56 px high.

    python3 -B logo_words.py

A Spanish console reads logos/es first (layout.logo_file); any other reads these.
"""
import subprocess
import tempfile
from pathlib import Path

from layout import HERE, RED

FONT = RED / "fonts/Roboto-BlackItalic.ttf"
WORDS = {
    "auto-allgames": ("ALL", "GAMES"),
    "auto-continue": ("GAMES TO", "CONTINUE"),
    "auto-favorites": ("CHEF'S", "PICKS"),
    "auto-lastplayed": ("RECENTLY", "PLAYED"),
    "emulators": ("MY", "EMULATORS"),
    "imageviewer": ("MY", "SCREENSHOTS"),
    "tools": ("MY", "TOOLS"),
}
SMALL, LARGE = (27, 1), (42.5, -1)     # point size and letter spacing of each line, measured on the Spanish ones
LARGE_TOP, HEIGHT, MAX_WIDTH = 25, 56, 296


def line(text, size, path):
    points, kerning = size
    subprocess.run(["magick", "-density", "72", "-background", "none", "-fill", "white", "-font", str(FONT),
                    "-pointsize", str(points), "-kerning", str(kerning), "label:" + text, "-trim", "+repage",
                    str(path)], check=True)
    return int(subprocess.check_output(["magick", str(path), "-format", "%w", "info:"], text=True))


def draw(name, small, large, folder):
    with tempfile.TemporaryDirectory() as temp:
        top, bottom = Path(temp) / "top.png", Path(temp) / "bottom.png"
        width = max(line(small, SMALL, top), line(large, LARGE, bottom))
        command = ["magick", "-size", f"{width}x{HEIGHT}", "xc:none", str(top), "-geometry", "+0+0", "-composite",
                   str(bottom), "-geometry", f"+0+{LARGE_TOP}", "-composite"]
        if width > MAX_WIDTH:
            command += ["-resize", f"{MAX_WIDTH}x"]
        subprocess.run(command + ["-strip", "-define", "png:exclude-chunks=date,time", str(folder / (name + ".png"))],
                       check=True)


if __name__ == "__main__":
    for name, (small, large) in WORDS.items():
        draw(name, small, large, HERE / "logos")
