# Build the Canica frontend

[Install the RC42 kit](../../docs/canica-rg35xx-h.md) · [Watch it on the handheld](../../docs/canica-en-accion.md)

Use Git, Python 3, Bash and Docker with Linux ARM64 support. Start in an empty directory containing the original RG35XX H Scarab image. The commands check its digest, build the pinned frontend with the four firmware patches and assemble the manual installation kit. [Download the May 11 image](https://github.com/knulli-cfw/knulli-linux/releases/download/20260511/knulli-h700-rg35xx-h-scarab-20260511.img.gz)

```bash
(
set -eu
git init -q firmware
git -C firmware remote add origin https://github.com/eduarbo/knulli-linux.git
git -C firmware sparse-checkout set tools/canica package/emulationstation/knulli-emulationstation
git -C firmware fetch --depth 1 --filter=blob:none origin 290505da065d33340045512c855abd1095e40f38
git -C firmware checkout -q --detach FETCH_HEAD
git clone --single-branch --branch main https://github.com/eduarbo/batocera-emulationstation.git frontend
git -C frontend checkout --detach 4f18ea3875435100768925da15e0813800371f86
scarab_patches=1f16d1a77df3c8f3432f0176117561f9c30c066d
git -C firmware fetch --depth 1 origin "$scarab_patches"
mkdir patches
git -C firmware archive "$scarab_patches:package/emulationstation/knulli-emulationstation" | tar -x -C patches
for patch in "$PWD"/patches/*.patch; do
    git -C frontend apply "$patch"
done
git -C frontend submodule update --init --recursive
git clone https://github.com/eduarbo/knulli-console-bundles.git tools
git -C tools checkout --detach 5942f8a9681d0cfcb52f4658f56d32b367bdcd69
image="$PWD/knulli-h700-rg35xx-h-scarab-20260511.img.gz"
python3 - "$image" <<'PY'
import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], 'rb') as src:
    for data in iter(lambda: src.read(1024 * 1024), b''):
        h.update(data)
if h.hexdigest() != 'c28a96f88b07e3adb4ea76b9874cd18ae177ec216bec2dac87c68795fb81291c':
    sys.exit("Image does not match RG35XX H Scarab 20260511")
PY
unit=tools/units/07-es-api-events/install
mkdir bin
DOCKER_DEFAULT_PLATFORM=linux/arm64 bash "$unit/build/build-es.sh" "$image" "$PWD/frontend" "$PWD/bin"
bash firmware/tools/canica/prepare-kit.sh tools bin/emulationstation canica-kit
)
```

The resulting frontend is `canica-kit/payload/emulationstation`. The build writes a manifest. The same four patches are applied by Buildroot for the full H700 firmware. The handheld kit uses a separate, sealed binary identified in the [RC42 inventory](../../docs/canica-rg35xx-h.md#reproduce-this-build).

## Install or remove a manual build

1. Copy `canica-kit` to `share/system/canica-kit`. Choose a stock theme and disable any existing service that replaces the frontend. Reboot if you changed services.
2. Over SSH, run `cd /userdata/system/canica-kit && bash install.sh`. This method uses **ES_PATCHED**. Keep this directory for rollback. The ready-made kit uses **CANICA**. Choose one installation method.
3. If you have the theme, copy `es-theme-canica` into `share/themes/` and select it in User Interface Settings. Install the included save adapter over SSH:

```sh
src=/userdata/system/canica-kit/resume-emulatorlauncher
(
  set -eu
  dest=/userdata/system/configs/emulationstation/resume/emulatorlauncher
  printf '%s  %s\n' cc43ab2aff9a156e1942cf02990110f5b0b005b030cceca1838828b649b67079 "$src" | sha256sum -c -
  mkdir -p "$(dirname "$dest")"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    cmp -s "$src" "$dest" || { echo 'Existing adapter preserved. Compare the two versions.'; exit 1; }
  else
    cp "$src" "$dest"
    chmod 755 "$dest"
  fi
  test -x "$dest" && cmp -s "$src" "$dest" && echo 'Adapter ready'
)
```

To restore the previous frontend, select your previous theme, run `cd /userdata/system/canica-kit && bash rollback.sh` and reboot. If you installed the adapter manually, compare it with the kit’s copy before removing it. The packaged method also supplies the FN + START enable marker; a manual build needs the marker named by the theme while the service is active.

## Rebuild the theme and sealed archives

The RC42 source archive from the [release](https://github.com/eduarbo/canica/releases/latest) reproduces the theme without a game library. The qualifying build used ImageMagick 7.1.2-29 and librsvg 2.62.3. Extract `canica-1.0.1-rc42-fuentes.zip` into a new directory. Run these commands from that directory with Python 3.9 or newer. Set `kit` to your original, checksum-verified handheld ZIP.

```sh
kit=/path/to/canica-1.0.1-rc42-rg35xx-h.zip
python3 -B knulli/39-canica/build.py output
python3 -B knulli/39-canica/validate.py output/canica-1.0.1-rc42.zip
unzip -p "$kit" share/system/canica/bin/emulationstation > nativo/emulationstation
python3 -B knulli/39-canica/release.py nativo output/canica-1.0.1-rc42.zip dist
```

The RC42 check reproduced all three archives byte for byte. Repackaging uses the qualified ARM64 executable from the kit because the native compiler embeds a build timestamp. Expected SHA-256 values:

```text
36edf9b164fc98bd60ed0f9de59f21ce6212aba0ce5d5667bdd20ff5b6c755c4  canica-1.0.1-rc42.zip
6f1f741e220170c3ba50948c55fa4dde8b62f2d0c8625c6b4b80fc20d3c309d1  canica-1.0.1-rc42-rg35xx-h.zip
cd69be04a2d8826573b54afaf0fbdfbeee3c0005c2ad7216bd4b5e692334a3cc  canica-1.0.1-rc42-fuentes.zip
```

## Build the installer for Tools

From this repository:

```sh
python3 -B tools/canica/installer/build.py 'Instalar Canica.sh'
```

This constructs the lightweight installer with its save adapter. To embed a privately supplied kit, add `--kit /path/to/canica-1.0.1-rc42-rg35xx-h.zip`. The packager recognizes RC27.1 through RC42 by SHA-256.

The installer checks the device model, firmware and original executable, stages files on the data partition, verifies them and enables Canica for the next boot. Running the installer again recovers an interrupted transaction. ROMs, saves and theme preferences stay in place. Physical testing used an existing RG35XX H card; first boot on a freshly flashed card remains unverified.
