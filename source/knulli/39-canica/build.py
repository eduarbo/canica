#!/usr/bin/env python3
"""Build an installable, reproducible Canica theme from an explicit asset list."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import theme_options as setting
from artwork import generate
from games import card_sizes, games, save_cards, tile_badge_geometry
from switcher import game_switcher
from layout import (ART, CAT, COL, FONT, HERE, HOME, KIT, LOOK, MONO_FONT, RED, element, option, prop,
                    system_data, systems, variables, view)

VERSION="1.0.1-rc37"
KIT["label"]=VERSION.rsplit("-",1)[-1].upper()
# The theme and its art are CC BY-SA 4.0; the project's own code is MIT.
LICENSES=("CC-BY-SA-4.0.txt","MIT.txt")
FOLDER="es-theme-canica"


def make_screen(root):
    screen=view(root,"screen")
    element(screen,"text","clock",{"visible":"false"},extra=False)
    element(screen,"batteryIndicator","batteryIndicator",{"visible":"false"},extra=False)
    for child in ET.parse(HOME/"home.xml").find(".//view[@name='screen']"):
        screen.append(child)
    for child in ET.parse(COL/"columns.xml").find(".//view[@name='screen']"):
        screen.append(child)
    indicators=screen.find("stackpanel[@name='u37Indicators']")
    if indicators is not None:indicators.find("pos").text="0.59375 0.01771"
    for n in screen.iter():
        if n.tag=="fontPath":n.text=FONT+"Bold.ttf"
        elif n.text and "/art/status/" in n.text:n.text=ART+n.text.rsplit("/",1)[1]
        elif n.tag=="iconPath":n.text=ART+"games.png"
        elif n.tag in ("fillColor","borderColor"):n.text="${accent}"
        elif n.tag=="backgroundColor":n.text="${top}"
    notice=screen.find("notification[@name='notification']")
    # A light opaque surface stands apart from the status bar and dark game art.
    for tag,value in {"pos":"0.5 0.145833","origin":"0.5 0","size":"0.90625 0.079167",
                      "fontSize":"0.02760","color":"${ctaInk}","backgroundColor":"${accent}",
                      "borderColor":"${ctaInk}","iconPath":LOOK+"notice.png","iconSize":"0.03750"}.items():
        notice.find(tag).text=value

    meter=screen.find("notification[@name='meters']")
    for tag,value in {"size":"0.08125 0.316667","iconSize":"0.03750","fontSize":"0.02552",
                      "color":"${ctaInk}","backgroundColor":"${accent}","borderColor":"${ctaInk}",
                      "trackColor":"${meterTrack}","fillColor":"${ctaInk}"}.items():
        meter.find(tag).text=value
    prop(meter,"trackBorderColor","${ctaInk}")
    # The updater's terminal: a monospaced window over the dimmed screen, lit in the palette's accent.
    # fillColor is that light (prompts, gauge, focus), trackColor the unlit gauge, trackBorderColor the dimming.
    console=ET.SubElement(screen,"notification",{"name":"console"})
    for tag,value in {"pos":"0.5 0.5","origin":"0.5 0.5","size":"0.89375 0.741667","fontPath":MONO_FONT,
                      "fontSize":"0.03125","color":"${ink}","backgroundColor":"${top}f6","borderColor":"${accent}96",
                      "fillColor":"${accent}","trackColor":"${rail}96","trackBorderColor":"${canvas}de",
                      "cornerSize":"${consoleCorner}"}.items():
        prop(console,tag,value)


def make_menu(root, dest, palettes):
    # Use the complete Scarab menu, including the widget skins for nested dialogs.
    menu=ET.parse(RED/"parts/menu.xml").find("view")
    root.append(menu)
    weights={"blackitalic":"Black","semibold":"SemiBold","medium":"Medium",
             "extrabold":"ExtraBold","bold":"Bold"}
    colors={"f3f4fc":"${ink}","e9ecf7":"${ink}","b5bece":"${muted}","8a95aa":"${muted}",
            "cfcbff":"${accent}","07111d80":"${menuGroup}","cbd3f014":"${menuLine}",
            "cbd3f01f":"${menuLine}","cbd3f026":"${menuLine}","cbd3f055":"${rail}"}
    resources={}
    for field in menu.iter():
        value=field.text or ""
        if value.startswith("${u36}/art/"):
            kind,filename=value.rsplit("/",2)[1:]
            resources[filename]=RED/"art"/kind/filename
            field.text=LOOK+"menu/"+filename
        elif value.startswith("${u36."):
            field.text=FONT+weights[value[6:-1]]+".ttf"
        elif value in colors:
            field.text=colors[value]
    # Keep the search keyboard independent of text entry in system configuration dialogs.
    for name,cap in (("searchKeys","search-key"),("searchActions","search-action")):
        element(menu,"menuKeyboard",name,{"path":LOOK+cap+".png","focusedPath":LOOK+"search-focus.png",
                "activePath":LOOK+"search-active.png","cornerSize":"6 6","spacing":"5",
                "color":"${ink}","selectedColor":"${ctaInk}"},extra=False)
    save_cards(menu)
    for look,palette in palettes.items():
        directory=dest/"art"/look/"menu"
        directory.mkdir()
        stops=palette.get("menuStops",[])
        lut=bytearray(b"P6\n256 1\n255\n")
        for (low,start),(high,end) in zip(stops,stops[1:]):
            for level in range(low,high):
                mix=(level-low)/(high-low)
                lut.extend(round(a+(b-a)*mix) for a,b in zip(bytes.fromhex(start),bytes.fromhex(end)))
        if stops:
            lut.extend(bytes.fromhex(stops[-1][1]))
        for filename,src in resources.items():
            target=directory/filename
            if not stops or filename in ("fade.png","scrim.png"):
                shutil.copyfile(src,target)
            else:
                # Preserve the silhouette and alpha of the approved skin. Remap luminance
                # through the warm palette, including the light edges of focused controls.
                subprocess.run(["magick",str(src),"-grayscale","Rec709Luma","-colorspace","sRGB","ppm:-",
                                "-channel","RGB","-clut","+channel","-strip","-define",
                                "png:exclude-chunks=date,time",str(target)],input=lut,check=True)


def xml(root,path):
    ET.indent(root,space="  ")
    ET.ElementTree(root).write(path,encoding="utf-8",xml_declaration=True)


def build(dest):
    palettes=json.loads((HERE/"palettes.json").read_text())
    generate(dest/"art",palettes)
    # Entries in a single system grid bind to each tile's console at runtime.
    # Supply its documented year when a frontend omits the optional release field.
    years=dest/"art/years"
    years.mkdir()
    rendered={}
    for details in CAT["systems"].values():
        year,theme=details.get("year"),details.get("theme")
        if not year or not theme:
            continue
        target=years/(theme+".png")
        if year in rendered:
            if target != rendered[year]:shutil.copyfile(rendered[year],target)
            continue
        subprocess.run(["magick","-size","32x15","xc:none","-fill","#17130f",
                        "-draw","roundrectangle 0,0 31,14 2,2","-font",str(RED/"fonts/Roboto-Bold.ttf"),
                        "-pointsize","10.5","-fill","#ffdb9e","-gravity","center","-annotate","+0+0",str(year),
                        "-strip","-define","png:exclude-chunks=date,time",str(target)],check=True)
        rendered[year]=target
    shutil.copytree(COL/"art/cardfx", dest/"art/display")
    fonts=dest/"fonts"
    fonts.mkdir()
    for name in ("Roboto-Regular.ttf","Roboto-Bold.ttf","Roboto-Black.ttf","Roboto-SemiBold.ttf","Roboto-Medium.ttf","Roboto-ExtraBold.ttf","OFL.txt"):
        shutil.copyfile(RED/"fonts"/name,fonts/name)
    for asset in ("D-DINCondensed-Bold.ttf","D-DIN-OFL.txt","IBMPlexMono-Medium.otf","IBMPlexMono-OFL.txt"):
        shutil.copyfile(HERE/"fonts"/asset,fonts/asset)
    # Console logos from Art Book Next (CC BY-NC-SA 2.0), with their credit; see logos/README.md.
    shutil.copytree(HERE/"logos", dest/"art/logos")
    licenses=dest/"licencias"
    licenses.mkdir()
    for name in LICENSES:
        shutil.copyfile(HERE/"licencias"/name,licenses/name)
    # Transparent component skins from the approved designs; all library content stays live.
    for look in palettes:
        for asset in ("chord","a","x","y","panel"):
            name=asset+".png"
            shutil.copyfile(HERE/"controls"/look/name,dest/"art"/look/name)
    for key in ("l1","r1","l2","r2"):
        shutil.copyfile(COL/"art"/("trigger-"+key+".png"),dest/"art"/(key+".png"))
    for name in ("battery-full","battery-at75","battery-at50","battery-at25","battery-empty","battery-incharge","wifi","wifi-off"):
        shutil.copyfile(HOME/"art/status"/(name+".png"),dest/"art"/(name+".png"))
    root=ET.Element("theme",defaultView="grid",defaultTransition="slide")
    prop(root,"formatVersion","7")
    # Subset IDs are the saved preferences of existing installations.
    option(root,setting.STYLE,"Variante",[(k,p["label"]) for k,p in palettes.items()])
    option(root,setting.DENSITY,"Tarjetas de juegos",[("grandes","Grandes"),("compacta","Compactas")])
    option(root,setting.VIDEO,"Vídeo en la tarjeta seleccionada",[("si","Reproducir"),("no","Solo imagen")])
    option(root,setting.ART,"Imagen de la ficha",[("portada","Carátula primero"),("captura","Captura primero")])
    option(root,setting.MOTION,"Vistas previas de consolas",[("animadas","Animadas"),("fijas","Solo imágenes fijas")])
    variables(root,{"detailPrimary":"thumbnail","detailFallback":"image","animateSystems":"1","stillSystems":"0"})
    variables(root,{"detailPrimary":"image","detailFallback":"thumbnail"},ifSubset=f"{setting.ART}:captura")
    variables(root,{"animateSystems":"0","stillSystems":"1"},ifSubset=f"{setting.MOTION}:fijas")
    for index,(key,p) in enumerate(palettes.items()):
        tokens={k:p[k] for k in ("canvas","panel","top","ink","muted","accent","rail","cardWash","frameCorner","tileRadius","ctaInk","meterTrack","menuGroup","menuLine")}
        tokens["consoleCorner"]=f"{int(p['tileRadius'])/480:.5f}"
        variables(root,{"look":key,**tokens},**({"ifSubset":f"{setting.STYLE}:{key}"} if index else {}))
    variables(root,{"videoDelay":"450"})
    variables(root,{"videoDelay":"-1"},ifSubset=f"{setting.VIDEO}:no")
    variables(root,{"decorations":"/userdata/decorations/canica"})
    variables(root,{"decorations":"/userdata/decorations/fosforo"},
              **{"if":'exists("/userdata/decorations/fosforo") && !exists("/userdata/decorations/canica")'})
    system_data(root)
    card_sizes(root)
    tile_badge_geometry(root)
    systems(root)
    games(root)
    game_switcher(root)
    helpers=view(root,"system,grid")
    element(helpers,"helpsystem","help",{"pos":"0 1.5","textColor":"00000000","iconColor":"00000000"},extra=False)
    make_screen(root)
    make_menu(root,dest,palettes)
    # ES evaluates variables before registering subsets in the same XML file.
    # Load them after the root has registered its defaults for a fresh install.
    bindings=ET.Element("theme")
    for block in list(root.findall("variables")):
        root.remove(block)
        bindings.append(block)
    root.insert(list(root).index(root.find("view")),ET.Element("include"))
    root.find("include").text="./bindings.xml"
    shutil.copyfile(HERE/"card_screens.py",dest/"card_screens.py")
    shutil.copyfile(HERE/"Preparar fondos de Canica.sh",dest/"Preparar fondos de Canica.sh")
    xml(bindings,dest/"bindings.xml")
    xml(root,dest/"theme.xml")
    shutil.copyfile(HERE/"gamesplash.xml",dest/"gamesplash.xml")
    guide=(HERE/"README.md").read_text().split("## Compilar desde el repositorio de origen",1)[0]
    (dest/"README.md").write_text(guide.rstrip()+"\n",encoding="utf-8")
    return root


def package(output):
    output.mkdir(parents=True,exist_ok=True)
    name=f"canica-{VERSION}.zip"
    with tempfile.TemporaryDirectory() as temp:
        dest=Path(temp)/FOLDER
        dest.mkdir()
        build(dest)
        with zipfile.ZipFile(Path(temp)/name,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for path in sorted(dest.rglob("*")):
                if path.is_file():
                    member=zipfile.ZipInfo(path.relative_to(temp).as_posix(),(2026,1,1,0,0,0))
                    member.external_attr=(0o100755 if path.name=="Preparar fondos de Canica.sh" else 0o100644)<<16
                    member.compress_type=zipfile.ZIP_DEFLATED
                    archive.writestr(member,path.read_bytes(),compresslevel=9)
        shutil.copyfile(Path(temp)/name,output/name)
    digest=hashlib.sha256((output/name).read_bytes()).hexdigest()
    (output/(name+".sha256")).write_text(f"{digest}  {name}\n")
    print(digest,name)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("output",type=Path)
    package(parser.parse_args().output)
