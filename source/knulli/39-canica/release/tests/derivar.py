"""Derive the next kit from a kit, for the update rehearsal only: same files, another version.

usage: derivar.py KIT.zip LABEL OUT_DIR   ->  prints the new ZIP's path

The kit says its version in system/canica/release, its inventory seals every file and its
service carries the inventory's digest: the three change together, as in a real release.
A derived kit is never published.
"""
import hashlib
import sys
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def derive(kit, label, out):
    with zipfile.ZipFile(kit) as z:
        files = {name: z.read(name) for name in z.namelist()}
    prefix = 'share/system/canica/'
    version = '1.0.1-' + label.lower()
    old_inventory = files.pop(prefix + 'SHA256SUMS')
    files[prefix + 'release'] = ('VERSION=%s\nLABEL=%s\n' % (version, label)).encode()
    sealed = {n: d for n, d in files.items() if n.startswith(('share/themes/', prefix))}
    inventory = ''.join('%s  %s\n' % (sha(d), n[6:]) for n, d in sorted(sealed.items())).encode()
    files[prefix + 'SHA256SUMS'] = inventory
    service = files['share/system/services/canica'].decode()
    assert service.count(sha(old_inventory)) == 1, 'the service does not carry its inventory digest'
    files['share/system/services/canica'] = service.replace(sha(old_inventory), sha(inventory)).encode()
    target = Path(out) / ('canica-%s-rg35xx-h.zip' % version)
    with zipfile.ZipFile(target, 'w') as z:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, data)
    return target


if __name__ == '__main__':
    print(derive(sys.argv[1], sys.argv[2], sys.argv[3]))
