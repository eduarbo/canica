#!/bin/bash
# Run on the build computer. Only the disposable Linux VM container receives mount privileges.
set -euo pipefail
if [ "$#" -ne 3 ]; then
    echo "Uso: bash probar-servicio.sh IMAGEN-SCARAB.img.gz KIT.zip fat_extract.py" >&2
    exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
kit=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
image_sha=c28a96f88b07e3adb4ea76b9874cd18ae177ec216bec2dac87c68795fb81291c
python3 - "$1" "$image_sha" <<'PY'
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
python3 -I "$3" "$1" 147456 BOOT/KNULLI "$work/scarab.squashfs"
docker run --rm --platform linux/arm64 --cap-add SYS_ADMIN \
    -v "$work:/qa:ro" -v "$here:/checks:ro" -v "$kit:/dist/kit.zip:ro" \
    debian:bookworm-slim bash -euc '
    apt-get update -qq
    apt-get install -yqq --no-install-recommends squashfs-tools unzip python3 util-linux > /dev/null
    bash /checks/stock.sh
    python3 /checks/lifecycle.py
'
