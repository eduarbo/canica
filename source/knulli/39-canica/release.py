"""Assemble the RG35XX-H distribution and its build sources from explicit inputs."""
import argparse
import base64
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build import FOLDER, LICENSES as OWN_LICENSES, VERSION
from layout import CAT, COL, HERE, HOME, KNULLI, PORTABLE_DESCRIPTIONS, RED
from validate import validate

PUBLIC = HERE / "release"
ENGINE_SHA = "f3b59db12e3ad04cb1afa29b6170b7db00b0afc815af76feff55c985c538c991"
WATCHDOG = KNULLI / "07-es-api-events/install/files/launcher.sh"
LICENSES = ("LICENSE.md", "CREDITS.md", "external/id3v2lib/LICENSE",
            "external/libcheevos/rcheevos/LICENSE", "external/nanosvg/nanosvg_license.txt",
            "external/pugixml/LICENSE.md")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive(output, members):
    with zipfile.ZipFile(output, "w") as z:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(str(name), (2026, 1, 1, 0, 0, 0))
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, data, compresslevel=9)


def native_sources(tree):
    files = {}
    for path in sorted(tree.rglob("*")):
        rel = path.relative_to(tree)
        if not path.is_file() or path.is_symlink() or any(s.startswith(".") for s in rel.parts):
            continue
        if rel.parts[0] in {"CMake", "es-app", "es-core", "external", "locale"}:
            if rel.parts[:2] == ("external", "pugixml") and len(rel.parts) > 3 and rel.parts[2] != "src" and str(rel) != "external/pugixml/scripts/pugixml.pc.in":
                continue
            if path.suffix.lower() not in {".h", ".hpp", ".inl", ".c", ".cpp", ".cc", ".inc", ".in", ".cmake",
                                           ".txt", ".po", ".pot", ".sh", ".md", ".rc", ".mm", ".m"} and path.name != "LICENSE":
                continue
        elif str(rel) not in {"CMakeLists.txt", *LICENSES, "resources/gamesdb.xml", "resources/checkWheelGunGamesResources.py"}:
            continue
        files[str(rel)] = path.read_bytes()
    return files


def license_headers(files):
    notices = {}
    for name, data in files.items():
        if Path(name).suffix not in {".h", ".hpp", ".cpp", ".c", ".inl", ".inc"}:
            continue
        content = data.decode("utf-8", "replace")
        for match in re.finditer(r"/\*.*?\*/|(?:^\s*//[^\n]*\n)+", content, re.DOTALL | re.MULTILINE):
            comment = match[0].strip()
            if re.search(r'copyright|SPDX-License-Identifier|permission is hereby granted|redistribution and use', comment, re.I):
                notices.setdefault(comment, name)
    return "\n\n".join(f"{name}\n{notice}" for notice, name in notices.items()).encode()


def theme_sources():
    paths = [HERE / f for f in ("build.py", "switcher.py", "card_screens.py", "Preparar fondos de Canica.sh", "release.py", "validate.py", "layout.py", "games.py", "artwork.py",
             "utility_art.py", "theme_options.py", "check-word-completion.cpp", "check-time-centering.py", "README.md", "palettes.json", "gamesplash.xml")]
    paths += list((HERE / "controls").glob("*/*.png")) + list((HERE / "fonts").glob("*")) + [HERE / "licencias" / n for n in OWN_LICENSES] + sorted((HERE / "logos").glob("*"))
    paths += [p for p in PUBLIC.iterdir() if p.is_file()]
    paths += sorted((PUBLIC / "keys").glob("*.pub"))
    paths += sorted(p for p in (PUBLIC / "tests").iterdir() if p.suffix in {".py", ".sh"})
    paths += [WATCHDOG, RED / "parts/menu.xml", *sorted((RED / "fonts").glob("Roboto-*.ttf")), RED / "fonts/OFL.txt"]
    for n in ET.parse(RED / "parts/menu.xml").iter():
        if (n.text or "").startswith("${u36}/art/"):
            paths.append(RED / n.text.removeprefix("${u36}/"))
    paths += sorted((COL / "art/cardfx").glob("*.png"))
    paths += [COL / "art" / f"trigger-{k}.png" for k in ("l1", "r1", "l2", "r2")]
    paths += [HOME / "art/status" / (k + ".png") for k in (
        "battery-full", "battery-at75", "battery-at50", "battery-at25", "battery-empty", "battery-incharge", "wifi", "wifi-off")]
    files = {"knulli/" + str(p.relative_to(KNULLI)): p.read_bytes() for p in paths}
    # The private design catalogue also contains personal media selections. Export only the public inputs.
    catalogue = {"tabs": [{k: t[k] for k in ("name", "systems")} for t in CAT["tabs"]]}
    for group in ("grouped", "systems"):
        catalogue[group] = {}
        for key, row in CAT[group].items():
            if isinstance(row, dict):
                fields = {k: row[k] for k in ("desc", "label", "year", "theme") if k in row}
                if key in PORTABLE_DESCRIPTIONS:
                    fields["desc"] = PORTABLE_DESCRIPTIONS[key]
                catalogue[group][key] = fields
    files["knulli/37-home-redesign/tools/home.json"] = json.dumps(catalogue, ensure_ascii=False, indent=2).encode()
    for template in (HOME / "home.xml", COL / "columns.xml", COL / "gamelist.xml"):
        original = ET.parse(template)
        out = ET.Element("theme")
        if template.name == "gamelist.xml":
            out.extend(n for n in original.findall("variables") if n.get("ifSubset", "").startswith("u38cardscale:"))
        else:
            out.append(original.find(".//view[@name='screen']"))
            if template.name == "columns.xml":
                view = ET.SubElement(out, "view", name="system")
                view.extend(n for n in original.find(".//view[@name='system']") if n.get("name", "").startswith(
                    ("u38UtilityCount", "u38LibraryContents", "u38App", "u38Latest", "u38EmptyShots")))
        files["knulli/" + str(template.relative_to(KNULLI))] = ET.tostring(out, encoding="utf-8")
    return files


ED25519_SPKI = bytes.fromhex("302a300506032b6570032100")   # the DER prefix of an Ed25519 public key


def ed25519_public(data):
    """The PEM of one Ed25519 public key, and nothing else."""
    text = data.decode("ascii")
    lines = [line.strip() for line in text.strip().splitlines()]
    if len(lines) < 3 or lines[0] != "-----BEGIN PUBLIC KEY-----" or lines[-1] != "-----END PUBLIC KEY-----":
        return False
    der = base64.b64decode("".join(lines[1:-1]), validate=True)
    return len(der) == 44 and der.startswith(ED25519_SPKI)


def channel_keys(folder):
    """The public keys a console trusts for kit updates: exactly the channel's key and its backup, so
    losing the first one does not strand the consoles in use. Only Ed25519 public keys."""
    keys = {path.name: path.read_bytes() for path in sorted(folder.glob("*.pub"))}
    if len(keys) != 2 or len(set(keys.values())) != 2 or not all(ed25519_public(data) for data in keys.values()):
        raise ValueError(f"En {folder} van exactamente las dos llaves públicas Ed25519 del canal: la de firma y la de respaldo.")
    return keys


def package(native, theme, output, keys=PUBLIC / "keys"):
    validate(theme)
    engine = (native / "emulationstation").read_bytes()
    if sha(engine) != ENGINE_SHA:
        raise ValueError("El frontend no coincide con la compilación cualificada.")
    output.mkdir(parents=True, exist_ok=True)
    source = native_sources(native / "fuente")
    with zipfile.ZipFile(theme) as z:
        payload = {"share/themes/" + name: z.read(name) for name in z.namelist()}
    prefix = "share/system/canica/"
    for name in LICENSES:
        payload[prefix + "avisos/" + name] = source[name]
    payload[prefix + "avisos/cabeceras.txt"] = license_headers(source)
    payload[prefix + "avisos/Canica.md"] = (PUBLIC / "AVISOS.md").read_bytes()
    # The launcher, the watchdog and the service are the project's own code.
    payload[prefix + "avisos/licencias/MIT.txt"] = (HERE / "licencias/MIT.txt").read_bytes()
    payload[prefix + "bin/emulationstation"] = engine
    payload[prefix + "launcher"] = (PUBLIC / "launcher").read_bytes()
    watchdog = WATCHDOG.read_text().replace(
        "Patched EmulationStation failed $failures times in a row: running stock, fixes 07/14/15 are off. It is tried again at the next boot if it worked before on this firmware. Log: /userdata/system/logs/es-patched.log",
        "Canica volvió al frontend de fábrica tras $failures fallos. Registro: /userdata/system/logs/canica.log")
    payload[prefix + "watchdog.sh"] = watchdog.encode()
    payload[prefix + "manifest"] = b"VERSION=scarab 2026/05/11 00:09\n"
    # The updater: what this kit is, who may sign the next one, and the program itself.
    payload[prefix + "release"] = f"VERSION={VERSION}\nLABEL={VERSION.rsplit('-', 1)[-1].upper()}\n".encode()
    payload[prefix + "updater.py"] = (PUBLIC / "updater.py").read_bytes()
    payload[prefix + "guard.py"] = (PUBLIC / "guard.py").read_bytes()
    for name, data in channel_keys(keys).items():
        payload[prefix + "keys/" + name] = data
    inventory = "".join(f"{sha(data)}  {name.removeprefix('share/')}\n" for name, data in sorted(payload.items())).encode()
    payload[prefix + "SHA256SUMS"] = inventory
    service = (PUBLIC / "canica").read_text()
    assert service.count("@INVENTORY_SHA256@") == 1
    payload["share/system/services/canica"] = service.replace("@INVENTORY_SHA256@", sha(inventory)).encode()
    payload["LEEME.md"] = payload["share/themes/" + FOLDER + "/README.md"]
    payload["AVISOS.md"] = (PUBLIC / "AVISOS.md").read_bytes()
    payload["PRUEBAS.md"] = (PUBLIC / "PRUEBAS.md").read_bytes()
    sources = theme_sources()
    sources.update({"nativo/fuente/" + name: data for name, data in source.items()})
    for name in ("build-es.sh", "fat_extract.py", "es-sdl-knulli.h"):
        sources["nativo/herramientas/" + name] = (native / "herramientas" / name).read_bytes()
    for number in range(111, 134):
        patch, = (native / "herramientas").glob(f"{number:04d}-*.patch")
        sources["nativo/herramientas/" + patch.name] = patch.read_bytes()
    sources["LEEME.md"] = (PUBLIC / "FUENTES.md").read_bytes()
    sources["AVISOS.md"] = payload["AVISOS.md"]
    sources["PRUEBAS.md"] = (PUBLIC / "PRUEBAS.md").read_bytes()
    with tempfile.TemporaryDirectory(dir=output) as temp:
        scratch = Path(temp)
        sums = []
        for suffix, files in (("rg35xx-h", payload), ("fuentes", sources)):
            name = f"canica-{VERSION}-{suffix}.zip"
            archive(scratch / name, files)
            sums.append(f"{sha((scratch / name).read_bytes())}  {name}\n")
        (scratch / "SHA256SUMS.txt").write_text("".join(sums))
        for path in sorted(scratch.iterdir(), key=lambda p: p.name == "SHA256SUMS.txt"):
            path.replace(output / path.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path, help="Directorio con emulationstation, fuente y herramientas")
    parser.add_argument("theme", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--keys", type=Path, default=PUBLIC / "keys",
                        help="Llaves públicas del canal (*.pub). Otra carpeta sólo para ensayos: ese kit no se publica.")
    args = parser.parse_args()
    package(args.native, args.theme, args.output, args.keys)
