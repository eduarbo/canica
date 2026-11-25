#!/bin/bash
# Run on the build computer. Rehearses an update inside the stock firmware: the updater of
# KIT (built with rehearsal keys) installs a kit derived from it, served by a local release
# server and signed with the rehearsal key. Only the disposable container gets mount rights.
set -euo pipefail
if [ "$#" -ne 5 ]; then
    echo "Uso: bash probar-actualizacion.sh IMAGEN-SCARAB.img.gz KIT.zip LLAVE-DE-ENSAYO.pem CARPETA-DEL-INSTALADOR fat_extract.py" >&2
    echo "  KIT.zip se empaqueta con release.py --keys y la llave pública de ensayo; la carpeta es tools/canica/installer de eduarbo/canica." >&2
    exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
kit=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
key=$(cd "$(dirname "$3")" && pwd)/$(basename "$3")
installer=$(cd "$4" && pwd)
python3 - "$1" c28a96f88b07e3adb4ea76b9874cd18ae177ec216bec2dac87c68795fb81291c <<'PY'
import hashlib,sys
h=hashlib.sha256()
with open(sys.argv[1],'rb') as stream:
    for block in iter(lambda: stream.read(1024*1024),b''):
        h.update(block)
if h.hexdigest()!=sys.argv[2]:
    raise SystemExit('Imagen de firmware incompatible')
PY
work=$(mktemp -d)
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
python3 -I "$5" "$1" 147456 BOOT/KNULLI "$work/scarab.squashfs"

# The next kit, its installer (which must know both kits) and its signed manifest
mkdir -p "$work/next" "$work/tool" "$work/ota/releases/canica-scarab-2026-05-11-00-09"
next=$(python3 -I "$here/derivar.py" "$kit" ENSAYO2 "$work/next")
cp -R "$installer/." "$work/tool/"
cp -R "$installer/../resume" "$work/resume"
python3 -I "$work/tool/admit.py" "$next" "$kit" --note 'rehearsal' >/dev/null
serial=2099010101
python3 -I "$work/tool/build.py" "$work/ota/releases/canica-scarab-2026-05-11-00-09/canica-$serial.sh" --kit "$next"
python3 -I - "$next" "$work/ota/releases/canica-scarab-2026-05-11-00-09" "$serial" <<'PY'
import hashlib, json, sys, time, zipfile
from pathlib import Path
kit, folder, serial = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
payload = folder / ('canica-%d.sh' % serial)
with zipfile.ZipFile(kit) as z:
    inventory = hashlib.sha256(z.read('share/system/canica/SHA256SUMS')).hexdigest()
manifest = dict(format=1, kind='canica-kit', model='Anbernic RG35XX-H', firmware='scarab 2026/05/11 00:09',
                version='1.0.1-ensayo2', label='ENSAYO2', serial=serial, min_serial=serial, inventory_sha256=inventory,
                created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), note='Ensayo de actualización.',
                payload=dict(name=payload.name, sha256=hashlib.sha256(payload.read_bytes()).hexdigest(), size=payload.stat().st_size))
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True) + '\n')
PY
openssl pkeyutl -sign -rawin -inkey "$key" -in "$work/ota/releases/canica-scarab-2026-05-11-00-09/manifest.json" \
    -out "$work/ota/releases/canica-scarab-2026-05-11-00-09/manifest.json.sig"

docker run --rm --platform linux/arm64 --cap-add SYS_ADMIN \
    -v "$work:/qa:ro" -v "$here:/checks:ro" -v "$kit:/dist/kit.zip:ro" -v "$work/ota:/ota:ro" \
    debian:bookworm-slim bash -euc '
    apt-get update -qq
    apt-get install -yqq --no-install-recommends squashfs-tools unzip python3 util-linux > /dev/null
    SOLO_ENTORNO=1 bash /checks/stock.sh
    python3 /checks/actualizacion.py
'
