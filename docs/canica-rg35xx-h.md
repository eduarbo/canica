# Install Canica on the RG35XX H

[Home](../README.md) · [Feature gallery](canica-en-accion.md) · [Build from source](../tools/canica/README.md)

Use an **Anbernic RG35XX H**, **KNULLI Scarab for May 11, 2026**, and the **Canica RC40 kit**. Canica runs locally with your own EmulationStation library. The kit supplies the patched frontend, theme and service; the installer adds the save adapter. [Download the kit](https://github.com/eduarbo/canica/releases/latest). Its theme and artwork are licensed under CC BY-SA 4.0 and its own code under the MIT License.

## Install

1. **Prepare the card.** An RG35XX H already running this Scarab release can keep its installation. For a new card, follow KNULLI’s flashing instructions for this exact model. RC40 shows an update’s progress as one of the theme’s notices, with a gauge. RC33 keeps each shelf’s suggestions for the whole day and shows its version under the library list. RC32 carries the console logos, RC31 rounded the focused card’s video in Iris, and RC30.1 added the license texts. RC30 is a release candidate tested on an existing handheld installation. A first cold boot on a freshly flashed microSD is still unverified. [RG35XX H image](https://github.com/knulli-cfw/knulli-linux/releases/download/20260511/knulli-h700-rg35xx-h-scarab-20260511.img.gz) · [KNULLI installation](https://knulli.org/play/install/)
2. **Copy the installer.** Download `canica-1.0.1-rc40-instalador.sh` from the [latest release](https://github.com/eduarbo/canica/releases/latest) and rename it `Instalar Canica.sh`: that single file holds everything. Or download `canica-1.0.1-rc40-rg35xx-h.zip` and copy it unopened beside the [lightweight installer](https://raw.githubusercontent.com/eduarbo/canica/main/tools/canica/Instalar%20Canica.sh), keeping both filenames.
3. **Put the file(s) in `share/roms/tools/`.** You can use the card’s data partition or enable **System Settings → Services → SAMBA** and connect to `smb://KNULLI/share` on a Mac or `\\KNULLI\share` on Windows. In that share, open `roms/tools`. [Transfer files to KNULLI](https://knulli.org/play/add-games/network-transfer/)
4. **Open Tools → Instalar Canica** and press **A**. If the tool is missing, open **START → Game Settings → Update Games Lists**. Wait for **“Canica está listo”** (Canica is ready), then restart. A message naming an existing conflicting file or frontend service means it was preserved. After an interruption, run the same installer again.
5. **Select the theme.** In **START → User Interface Settings → Theme Set**, choose **es-theme-canica**. Under Theme Configuration, pick **Iris** or **Ámbar** (Amber). Leave the default grid size on **Automatic** to retain the system-specific layouts. The other settings control card size, video in the selected card, cover or screenshot priority, and animated or static console previews.
6. **Check one game.** Open a populated system. **Y** opens the word-completion keyboard. **A** starts the selected game. **X** opens save management or explains that the system saves internally. On an SSH connection, `knulli-services status canica` reports the service status.

## Bring your own ROMs

Keep the ROM directory and file types the stock system supports. A Game Boy game goes in `share/roms/gb/`, for example. Refresh the games list after copying it. For a first test, use a game that already launches on Scarab with its required BIOS or runtime in place. Canica uses that same emulator setup. An existing EmulationStation catalog can be reused. Normal directory scanning also finds games without a `gamelist.xml`; leave “Parse gamelists only” disabled for that case. [KNULLI game storage](https://knulli.org/play/add-games/)

| What you want | What your library supplies |
| --- | --- |
| Browse, search and play | A supported ROM in the correct system directory. Search uses game titles and offers word completions. |
| Recently Played, console history and Chef’s Picks | Play a game to start history. Mark games as favorites to populate Chef’s Picks. FN + START resumes the most recent game when the shortcut is enabled. |
| A moving preview | A playable video referenced by the game’s `<video>` field. Enable video on the selected card. |
| Game Boy colors or portrait screenshots | Reference a screenshot with `<image>` or `<titleshot>` in a `screenshots`, `snaps`, `screens` or `titleshots` directory inside the system folder. During installation, Canica makes a four-tone green copy of Game Boy stills for the card cache. Rerun the installer after adding media. Your source images, videos and gameplay keep their own colors. |
| Stars, cover art and detail text | Your own rating, artwork and description. A game can still launch with these fields empty. |
| Dated save slots and screenshots | Create a state on an emulator that supports it. X shows its available slots. In-game saves also work on systems with their own save mechanism. |
| Console logos | Included: the kit carries Art Book Next’s logos (CC BY-NC-SA 2.0). Your own transparent PNG in `share/decorations/canica/logos/<system-theme>.png` replaces one; for GBA use `gba.png`. A system without a logo shows its name. |
| Hardware pictures like the recordings | Optional transparent PNGs in `share/decorations/canica/hardware/<system-theme>.png`. The ones in the recordings are my own decorations and are not part of the kit. |

Here is one ordinary catalog entry. The paths resolve relative to `share/roms/gb/gamelist.xml`. A video, favorite or rating can be added later.

```xml
<gameList>
  <game>
    <path>./Example.gb</path>
    <name>Example</name>
    <image>./media/screenshots/Example.png</image>
    <video>./media/videos/Example.mp4</video>
  </game>
</gameList>
```

## From the handheld to a TV with RomM

I use RomM as the shared library for my Anbernic and my TVs. Grout on the handheld handles synchronization. My custom TV launchers have their own game browser, so I can choose the same game from the sofa and continue a compatible save. RomM, Grout and the TV launchers run independently of the Canica installer. You can use every local library control with your own files and no RomM account. [RomM documentation](https://docs.romm.app/)

**What travels.** Save inside the game, exit so the emulator writes the file, and let the handheld finish syncing. On the TV, select the matching game and a launcher/core that supports that in-game save format. When returning to the handheld, let the newer save arrive before starting the game. For example, the TV adapters recognize supported Game Boy and Game Boy Color battery saves from Gambatte and standard SNES SRAM from Snes9x. They check the cartridge and expected save size before importing. Real-time-clock data and special-chip games need their own support. An emulator state can also depend on the exact core and build.

**Why A and X behave differently.** A recent local state can predate an in-game save that has just arrived from the TV. The adapter runs after the launcher’s game-start hooks and considers the local save history and, when available, Grout’s download record. A can preserve the newer in-game progress. X lets you deliberately restore an older compatible slot. [Save adapter source](../tools/canica/resume/emulatorlauncher)

## Reproduce this build

| Part | Exact input |
| --- | --- |
| Base system | RG35XX H Scarab `20260511` image, SHA-256 `c28a96f88b07e3adb4ea76b9874cd18ae177ec216bec2dac87c68795fb81291c` |
| Frontend | [EmulationStation `5e123f7`](https://github.com/eduarbo/batocera-emulationstation/tree/5e123f7) with the [four Scarab packaging patches](https://github.com/eduarbo/knulli-linux/tree/1f16d1a77df3c8f3432f0176117561f9c30c066d/package/emulationstation/knulli-emulationstation) |
| ARM64 build tools | [Bundle tools `5942f8a`](https://github.com/eduarbo/knulli-console-bundles/tree/5942f8a9681d0cfcb52f4658f56d32b367bdcd69) |
| Installer and save adapter | [RC40 recipe](https://github.com/eduarbo/canica/tree/v1.0.1-rc40/tools/canica) |
| Theme, artwork, engine and service | `canica-1.0.1-rc40-rg35xx-h.zip` · SHA-256 `8262a16a54e7b6d736fa1342ed81d2b2cc84dda6b95918b05580ea4aa15b2390` |

To compare the installed files over SSH, run the commands below. The manifest covers the frontend and packaged theme files. The last command checks the separately installed save adapter against the RC40 version, unchanged since RC30. If you deliberately kept a custom adapter, its hash will differ.

```sh
cd /userdata && sha256sum -c system/canica/SHA256SUMS
sha256sum /userdata/system/configs/emulationstation/resume/emulatorlauncher
# RC40 adapter: 4e36929f93928371f3d151fa7cd71b3198b9246b2fd74a0bd0d5870874613b8e
```

On the reference RG35XX H, all 382 installed RC30 kit and adapter files matched their packaged hashes, including the running frontend. An isolated test on the handheld used a small Game Boy program, restored a chosen slot, preserved a newer in-game save and generated a card from a separate test screenshot. These checks used no owner ROMs or RomM account.

RC30.1 keeps 377 of RC30’s 381 packaged files byte for byte, including the frontend, the launcher and every theme asset. It replaces the notices, the theme guide, the inventory and the checksum the service seals, and adds three license files. On a computer, the public installer placed it on an empty card folder and over RC27.1, RC27.2, RC28, RC29.1 and RC30, and every file matched the new inventory. The service checks passed in a disposable ARM64 Linux environment built from the Scarab image. On the reference RG35XX H, the installer then upgraded RC30 to RC30.1. After a restart the service started Canica, and all 385 installed kit and adapter files matched their packaged hashes, including the running frontend. RC31 reached that handheld through the signed update channel: its updater verified the manifest and ran the installer by itself, and afterwards all 385 files matched again.

The compiled frontend in this kit was built for RC40 from the revision above, SHA-256 `ff8eb0b23b3989cd7777f9461e5aba303a8d492bbcc3c908da914f682590153c`. The [source build guide](../tools/canica/README.md#rebuild-the-theme-and-sealed-archives) includes the verified commands and all three archive digests.

## Update

Download the newer installer and open it again from Tools. It replaces only the files an earlier Canica installed and keeps any you edited. My own console takes new kits by itself: a [signed channel](https://github.com/eduarbo/knulli-console-bundles#canica-kit-updates) names the next installer and a small updater on the handheld runs it when the menu is free. That updater is not packaged for other consoles yet.

## Return to the previous menu

Select your previous theme, disable **CANICA** in **System Settings → Services** and reboot. The installed files and your library stay on the card. The installer log is `share/system/logs/canica-instalacion.txt`. If you built and installed through the separate **ES_PATCHED** service, use the rollback script in the [build guide](../tools/canica/README.md#install-or-remove-a-manual-build).
