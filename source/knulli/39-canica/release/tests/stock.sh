#!/bin/bash
set -euo pipefail
[ -f /.dockerenv ] && [ -f /qa/scarab.squashfs ] && [ ! -e /sc/usr/bin/emulationstation ] || {
    echo "Ejecuta probar-servicio.sh en un contenedor nuevo" >&2
    exit 2
}
sc=/sc
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unsquashfs -f -q -n -d "$sc" /qa/scarab.squashfs 'lib/*.so*' 'lib/ld-linux*' 'usr/lib/lib*.so*' 'usr/lib/pulseaudio/*.so*' usr/bin/emulationstation 'bin/*' 'sbin/*' 'usr/share/knulli/knulli.version' 'usr/bin/knulli-*settings*' usr/bin/knulli-services 'usr/bin/busybox' usr/bin/coreutils usr/bin/sha256sum usr/bin/flock usr/bin/logger usr/bin/cmp usr/bin/cut usr/bin/tr usr/bin/find usr/bin/sort usr/bin/curl usr/bin/seq usr/bin/timeout usr/bin/awk usr/bin/head usr/bin/readlink usr/bin/dirname usr/bin/basename usr/bin/env usr/bin/killall usr/share/knulli/services 'etc/knulli.conf' >/tmp/unpack.log 2>&1
mkdir -p "$sc"/{userdata/system/logs,sys,proc,dev,run,var/run,tmp,etc} "$sc/sys/firmware/devicetree/base"
touch "$sc/etc/ld.so.conf"
ldconfig -r "$sc"
printf 'Anbernic RG35XX-H\0' > "$sc/sys/firmware/devicetree/base/model"
mountpoint -q "$sc/proc" || mount -t proc proc "$sc/proc"
mountpoint -q "$sc/var/run" || mount -t tmpfs tmpfs "$sc/var/run"
mountpoint -q "$sc/dev" || mount --bind /dev "$sc/dev"
cp -p /sc/usr/bin/emulationstation /tmp/initial-stock.engine
unzip -qo /dist/kit.zip 'share/*' -d /tmp/transfer
cp -a /tmp/transfer/share/. "$sc/userdata/"
printf 'system.services=canica\n' > "$sc/userdata/system/knulli.conf"
in_sc() { chroot "$sc" "$@"; }
svc=/userdata/system/services/canica
target=/usr/bin/emulationstation
stockhash=$(sha256sum /tmp/initial-stock.engine | cut -d' ' -f1)
check_stock() { test "$(sha256sum "$sc$target" | cut -d' ' -f1)" = "$stockhash"; }
check_stock
in_sc knulli-services list user | grep -Fi canica
mv "$sc/userdata/themes/es-theme-canica/art/l1.png" /tmp/missing-l1
if in_sc bash "$svc" start; then exit 8; fi
check_stock
mv /tmp/missing-l1 "$sc/userdata/themes/es-theme-canica/art/l1.png"
for other in es_patched fosforo; do
    printf 'system.services=canica %s\n' "$other" > "$sc/userdata/system/knulli.conf"
    if in_sc bash "$svc" start; then exit 9; fi
    check_stock
done
printf 'system.services=canica\n' > "$sc/userdata/system/knulli.conf"
printf 'Otro modelo\0' >"$sc/sys/firmware/devicetree/base/model"
if in_sc bash "$svc" start; then exit 10; fi
printf 'Anbernic RG35XX-H\0' >"$sc/sys/firmware/devicetree/base/model"
cp "$sc/usr/share/knulli/knulli.version" /tmp/version.original
echo distinto >"$sc/usr/share/knulli/knulli.version"
if in_sc bash "$svc" start; then exit 11; fi
cp /tmp/version.original "$sc/usr/share/knulli/knulli.version"
check_stock
mv "$sc/userdata/system/knulli.conf" /tmp/canica-test-config
if in_sc bash "$svc" start; then exit 12; fi
mv /tmp/canica-test-config "$sc/userdata/system/knulli.conf"
check_stock
printf 'otro ejecutable' > "$sc$target"
if in_sc bash "$svc" start; then exit 13; fi
cp /tmp/initial-stock.engine "$sc$target"
check_stock
in_sc knulli-services start canica
in_sc bash "$svc" status | grep 'preparado para el siguiente inicio'
in_sc bash "$svc" start
test "$sc$target" -ef "$sc/var/run/canica/launcher"
env LD_BIND_NOW=1 chroot "$sc" "$target" --help >/tmp/candidate-usage
grep '^Version' /tmp/candidate-usage
test "$(sha256sum "$sc/var/run/canica/bin/emulationstation" | cut -d' ' -f1)" = da85c76166dfd47928f660ecb90d2a929deb527298542e1b4a3f8b6486871df0
in_sc knulli-services stop canica
check_stock
env LD_BIND_NOW=1 chroot "$sc" "$target" --help >/tmp/stock-usage
grep '^Version' /tmp/stock-usage
in_sc bash "$svc" stop
echo 'modelo, versión, conflicto, copia truncada, servicio nativo, doble activación, ejecutable ARM64 y vuelta a stock: correctos'
