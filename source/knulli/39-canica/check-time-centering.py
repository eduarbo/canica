"""Check the visible clock, duration and caption on native 640 × 480 Canica captures."""

from pathlib import Path
import subprocess
import sys


def visible_columns(pixels, left, right, top, bottom):
    result = []
    for x in range(left, right):
        for y in range(top, bottom):
            pixel = pixels[(y * 640 + x) * 3 : (y * 640 + x) * 3 + 3]
            if min(pixel) > 65 and max(pixel) > 140:
                result.append(x)
                break
    return result


def check(capture,header_only=False):
    bitmap = subprocess.check_output(
        ["magick", str(capture), "-alpha", "off", "-depth", "8", "ppm:-"]
    )
    header = b"P6\n640 480\n255\n"
    pixels = bitmap[len(header) :]
    if not bitmap.startswith(header) or len(pixels) != 640 * 480 * 3:
        raise ValueError(f"{capture}: expected a 640 × 480 native capture")
    if header_only:
        for index,caption in enumerate(("juegos","favs","jugados")):
            left=311+67*index
            group=visible_columns(pixels,left,left+67,33,50)
            label=visible_columns(pixels,left,left+67,51,63)
            if not group or not label:
                raise ValueError(f"Missing header counter {caption}")
            delta=(group[0]+group[-1]-label[0]-label[-1])/2
            print(f"{capture.name} {caption}: {delta:+.1f} px")
            if abs(delta)>1:
                raise ValueError(f"Caption not centered under {caption}")
        return
    run = visible_columns(pixels, 55, 146, 280, 296)
    caption = visible_columns(pixels, 72, 128, 298, 311)
    if not run or not caption:
        raise ValueError(f"{capture}: clock or caption missing")
    delta = (run[0] + run[-1] - caption[0] - caption[-1]) / 2
    print(f"{capture.name}: {delta:+.1f} px")
    if abs(delta) > 1 or not any(
        x + 1 not in run and x + 2 not in run for x in run[:17] if x < run[-1] - 4
    ):
        raise ValueError(
            "Expected the clock and its value to be separated and centered over the caption"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: check-time-centering.py CAPTURE.png [CAPTURE.png ...]")
    header_only=sys.argv[1]=="--header"
    for filename in sys.argv[2 if header_only else 1:]:
        check(Path(filename),header_only)
