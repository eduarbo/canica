"""Prepare system and game card screenshots from the local library."""

import fcntl
import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

COUNT = 5
FRAME = (144, 140)
HANDHELD = dict(
    gb=10 / 9,
    gbc=10 / 9,
    gba=3 / 2,
    gamegear=10 / 9,
    atarilynx=160 / 102,
    ngpc=160 / 152,
    wonderswan=224 / 144,
    wonderswancolor=224 / 144,
    wswan=224 / 144,
    nds=4 / 3,
    pico8=1,
)
CRT = set(
    "arcade arcadetate auto-verticalarcade mame nes fds snes megadrive genesis mastersystem neogeo atari2600 sega32x segacd psx n64 pcengine pce-cd dreamcast".split()
)
TATE = {"arcadetate", "auto-verticalarcade"}
PALETTES = {
    "gb": ("1a3318", "4e692a", "90ac48", "c9dc83"),
    "wonderswan": ("252522", "5f6252", "969a84", "d1d3be"),
}


def community_images(root):
    systems = {}
    for folder in (
        Path("/usr/share/emulationstation"),
        root / "system/configs/emulationstation",
    ):
        for file in sorted(folder.glob("es_systems*.cfg")):
            try:
                for node in ET.parse(file).getroot().findall("system"):
                    name = node.findtext("name")
                    theme = node.findtext("theme") or name
                    if all(
                        x and x not in (".", "..") and x == Path(x).name
                        for x in (name, theme)
                    ):
                        systems[name] = theme
            except (ET.ParseError, OSError):
                continue
    return systems


def candidates(system, theme):
    catalog = system / "gamelist.xml"
    if not catalog.is_file():
        return []
    result = []
    for _, game in ET.iterparse(catalog, events=("end",)):
        if game.tag != "game":
            continue
        title = (game.findtext("name") or "").casefold()
        path = game.findtext("image") or game.findtext("titleshot")
        if path and game.findtext("hidden") != "true":
            file = system / path
            if file.is_file():
                try:
                    rating = float(game.findtext("rating") or 0)
                except ValueError:
                    rating = 0
                priority = (
                    theme == "eduke32" and title == "duke nukem 3d",
                    game.findtext("favorite") == "true",
                    bool(game.findtext("lastplayed")),
                    rating,
                )
                result.append((priority, title, file))
        game.clear()
    result.sort(key=lambda x: (tuple(-v for v in x[0]), x[1]))
    return [row[2] for row in result]


def display_image(source, theme, bounds, keep_ds=False, cover=False):
    """The capture at its console's display aspect, inside bounds; with cover, at least as large as bounds in
    both directions (the caller cuts it)."""
    with Image.open(source) as src:
        im = src.convert("RGB")
    w, h = im.size
    if theme == "nds" and not keep_ds:
        if h / w > 1.3:
            im = im.crop((0, 0, w, h // 2))
        elif w / h > 2.2:
            im = im.crop((0, 0, w // 2, h))
    w, h = im.size
    aspect = w / h
    if theme == "nds" and keep_ds and (h / w > 1.3 or w / h > 2.2):
        aspect = w / h
    elif theme in TATE:
        aspect = 3 / 4 if h > w else aspect
    elif theme in HANDHELD:
        aspect = HANDHELD[theme]
        if h > w and theme in ("atarilynx", "wonderswan", "wonderswancolor", "wswan"):
            aspect = 1 / aspect
    elif theme in CRT and 0.85 <= aspect <= 1.65:
        aspect = 4 / 3
    key = "wonderswan" if theme == "wswan" else theme
    if key in PALETTES:
        shades = [bytes.fromhex(c) for c in PALETTES[key]]
        gray = ImageOps.grayscale(im)
        lut = [
            channel for level in range(256) for channel in shades[min(3, level // 64)]
        ]
        gray = Image.frombytes("P", gray.size, gray.tobytes())
        gray.putpalette(lut)
        im = gray.convert("RGB")
    elif theme in HANDHELD:
        saturation = {"gba": 0.8, "gbc": 0.88, "nds": 0.9}.get(theme, 0.92)
        im = ImageEnhance.Color(im).enhance(saturation)
    max_width, max_height = bounds
    if cover and aspect >= max_width / max_height:
        height = max_height
        width = max(max_width, round(max_height * aspect))
    elif cover:
        width = max_width
        height = max(max_height, round(max_width / aspect))
    else:
        width = max(1, min(max_width, round(max_height * aspect)))
        height = max(1, min(max_height, round(width / aspect)))
    return im.resize(
        (width, height),
        Image.Resampling.LANCZOS
        if w > width or h > height
        else Image.Resampling.NEAREST,
    )


def screen(source, theme):
    # A console card's background: the game screen at its display aspect, scaled to cover the whole card and
    # cut from the centre, so no band of the card is left without picture.
    shown = display_image(source, theme, FRAME, cover=True)
    left, top = (shown.width - FRAME[0]) // 2, (shown.height - FRAME[1]) // 2
    return shown.crop((left, top, left + FRAME[0], top + FRAME[1]))


def prepare_game_cards(share, systems):
    target = share / "decorations/canica-capturas/juegos"
    target.mkdir(parents=True, exist_ok=True)
    with (target / ".prepare.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return update_game_cards(share, systems, target)


def update_game_cards(share, systems, target):
    index = target / "index-v1.json"
    try:
        previous = json.loads(index.read_text())
    except (OSError, ValueError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    current = previous.copy()
    for number, (name, theme) in enumerate(systems.items()):
        print(f"@canica cards {number} {len(systems)}", flush=True)    # read by the kit updater's panel
        directory = share / "roms" / name
        if name in {"tools", "emulators", "imageviewer", "vaixterm"}:
            continue
        try:
            games = ET.parse(directory / "gamelist.xml").getroot()
        except (ET.ParseError, OSError):
            continue
        if games.tag != "gameList":
            continue
        retired = {rel for rel in previous if Path(rel).parts[:1] == (name,)}
        for game in games.findall("game"):
            entry = Path(game.findtext("path") or ".")
            if entry.is_absolute() or ".." in entry.parts or not entry.name:
                continue
            if not (directory / entry).exists():
                continue
            relative = str(Path(name) / entry) + ".png"
            if game.findtext("hidden") == "true":
                continue
            source = None
            for field in ("image", "titleshot"):
                value = game.findtext(field)
                if not value:
                    continue
                candidate = directory / value
                if candidate.resolve().is_relative_to(directory.resolve()) and any(
                    part.lower() in {"screenshots", "snaps", "screens", "titleshots"}
                    for part in candidate.parent.parts
                ):
                    source = candidate
                    break
            if source is None:
                continue
            retired.discard(relative)
            dest = target / relative
            if not dest.resolve().is_relative_to(target.resolve()):
                continue
            try:
                stat = source.stat()
                signature = [str(source), stat.st_size, stat.st_mtime_ns, theme]
                if previous.get(relative) != signature or not dest.is_file():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_name(f".card-{os.getpid()}.tmp")
                    try:
                        display_image(source, theme, (320, 320), keep_ds=True).save(tmp, "PNG", compress_level=2)
                        os.replace(tmp, dest)
                    finally:
                        tmp.unlink(missing_ok=True)
                current[relative] = signature
            except (OSError, ValueError, UnidentifiedImageError) as error:
                print(f"{name}/{entry}: {error}")
        for relative in retired:
            stale = target / relative
            if stale.suffix == ".png" and stale.resolve().is_relative_to(target.resolve()):
                stale.unlink(missing_ok=True)
                current.pop(relative, None)
    temporary = target / f".index-{os.getpid()}.tmp"
    try:
        temporary.write_text(json.dumps(current, ensure_ascii=False))
        os.replace(temporary, index)
    finally:
        temporary.unlink(missing_ok=True)
    return len(current)


def prepare(share):
    groups = {}
    systems = community_images(share)
    for name, theme in systems.items():
        if name in {"tools", "emulators", "imageviewer"}:
            continue
        try:
            images = candidates(share / "roms" / name, theme)
        except (ET.ParseError, OSError) as err:
            print(f"{name}: {err}")
            continue
        if images:
            groups.setdefault(theme, []).extend(images)
    # Ports aggregates native PC engines. Prefer an actual game to the PortMaster installer.
    if "ports" in groups:
        playable = [p for p in groups["ports"] if "portmaster" not in p.stem.casefold()]
        groups["ports"] = playable + groups.get("prboom", []) + groups["ports"]
    target = share / "decorations/canica-capturas"
    completed = 0
    for theme, images in groups.items():
        dest = target / theme
        dest.mkdir(exist_ok=True, parents=True)
        frames = []
        for src in dict.fromkeys(images):
            try:
                frame = screen(src, theme)
            except (OSError, ValueError, UnidentifiedImageError):
                continue
            frames.append(frame)
            if len(frames) == COUNT:
                break
        if not frames:
            continue
        for idx in range(COUNT):
            path = dest / f"{idx}.png"
            tmp = dest / f".{idx}.{os.getpid()}.tmp"
            try:
                frames[idx % len(frames)].save(tmp, "PNG")
                if not path.is_file() or path.read_bytes() != tmp.read_bytes():
                    os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)
        completed += 1
    print(f"Tarjetas de juegos con captura: {prepare_game_cards(share, systems)}")
    return completed


if __name__ == "__main__":
    print(f"Consolas con capturas preparadas: {prepare(Path('/userdata'))}")
