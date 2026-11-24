"""Teach the installer a new kit: its ZIP, and which untouched files of earlier kits it may replace.

usage: admit.py NEW_KIT.zip [EARLIER_KIT.zip ...] [--note TEXT] [--installer install.py]

Run once per release, with every published kit as an earlier one. It adds the new ZIP to
PACKAGES and, for each file that differs from an earlier kit, the earlier digest to PREVIOUS.
Entries already present are left alone, so running it again changes nothing.
"""
import argparse
import hashlib
import re
from pathlib import Path
from runpy import run_path
from zipfile import ZipFile


def digests(kit):
    with ZipFile(kit) as archive:
        return {name[6:]: hashlib.sha256(archive.read(name)).hexdigest()
                for name in archive.namelist() if name.startswith('share/') and not name.endswith('/')}


def admit(installer, new, earlier, note):
    known = run_path(str(installer))
    text = installer.read_text()
    name, kit_digest = new.name, hashlib.sha256(new.read_bytes()).hexdigest()
    if known['PACKAGES'].get(name, kit_digest) != kit_digest:
        raise SystemExit('%s is already listed with another digest' % name)
    if name not in known['PACKAGES']:
        text = text.replace('PACKAGES = {\n', "PACKAGES = {\n    '%s': '%s',\n" % (name, kit_digest), 1)
    fresh, added, count = digests(new), [], 0
    for path, digest in sorted(fresh.items()):
        before = {old[path] for old in map(digests, earlier) if path in old} - {digest}
        before -= known['PREVIOUS'].get((path, digest), set())
        if not before:
            continue
        count += len(before)
        key = "    ('%s',\n     '%s'): {\n" % (path, digest)
        lines = ''.join("        '%s',\n" % d for d in sorted(before))
        if key in text:
            text = text.replace(key, key + lines, 1)
        else:
            added.append(key + lines + '    },\n')
    if added:
        head = re.search(r'^PREVIOUS = \{\n', text, re.M)
        text = text[:head.end()] + '    # %s\n' % note + ''.join(added) + text[head.end():]
    installer.write_text(text)
    return name, count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('new', type=Path)
    parser.add_argument('earlier', type=Path, nargs='*')
    parser.add_argument('--note', default='')
    parser.add_argument('--installer', type=Path, default=Path(__file__).resolve().parent / 'install.py')
    args = parser.parse_args()
    name, count = admit(args.installer, args.new, args.earlier, args.note or args.new.name)
    print('%s admitted; %d earlier file versions added' % (name, count))
