#!/usr/bin/env python3
"""Check the distributable itself, including defaults, asset closure and native layout choices."""
import hashlib
import itertools
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

import theme_options as setting

LICENSES=("es-theme-canica/licencias/CC-BY-SA-4.0.txt","es-theme-canica/licencias/MIT.txt")


def require(ok,message):
    if not ok:raise ValueError(message)


def resolve_settings(root,selected,system):
    values={"themePath":"es-theme-canica"}
    for block in root.findall("variables"):
        condition=block.get("if","")
        if condition and ("'"+system+"'") not in condition:
            continue
        if "ifSubset" in block.attrib:
            key,value=block.get("ifSubset").split(":")
            if selected[key]!=value:
                continue
        values.update({n.tag:n.text or "" for n in block})
    return values


def validate(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        require(len(names)==len(set(names)) and not z.testzip(),"duplicate or damaged ZIP entry")
        for name in names:
            parts=PurePosixPath(name).parts
            require(parts[0]=="es-theme-canica" and ".." not in parts and len(parts)>1,"unexpected archive root")
            require((z.getinfo(name).external_attr>>28)==8,"unexpected file type")
            require(name in ("es-theme-canica/card_screens.py","es-theme-canica/Preparar fondos de Canica.sh",*LICENSES) or name.endswith((".png",".ttf","/OFL.txt","/D-DIN-OFL.txt","/theme.xml","/bindings.xml","/gamesplash.xml","/README.md")),"unexpected payload")
        root=ET.fromstring(z.read("es-theme-canica/theme.xml"))
        order=list(root)
        include=root.find("include")
        require(include is not None and include.text=="./bindings.xml","bindings include missing")
        require(max(order.index(s) for s in root.findall("subset")) < order.index(include) < order.index(root.find("view")),
                "register settings before including bindings")
        require(root.find(".//image[@name='preparedStill']") is not None and
                root.find(".//slideshow[@name='preparedSlides']") is not None, "missing prepared console art")
        root.extend(ET.fromstring(z.read("es-theme-canica/bindings.xml")))
        raw=ET.tostring(root,encoding="unicode")
        for forbidden in ("/Users/","/private/","/userdata/roms/","/userdata/system/","es-theme-tiled","factbox:","u38cardscale:","RomM","AirPods","Grout"):
            require(forbidden not in raw,"private or obsolete dependency: "+forbidden)
        builtins = {"themePath"}
        defined = {child.tag for block in root.findall("variables") for child in block}
        missing = set(re.findall(r"\$\{([^}]+)\}", raw)) - defined - builtins
        require(not missing, "unknown theme variables: " + ", ".join(sorted(missing)))
        options={s.get("name"):[i.get("name") for i in s] for s in root.findall("subset")}
        require(set(options)=={setting.STYLE,setting.DENSITY,setting.VIDEO,setting.ART,setting.MOTION},"unexpected options")
        for e in root.iter():
            if "ifSubset" in e.attrib:
                key,value=e.get("ifSubset").split(":")
                require(value in options.get(key,[]),"unreachable setting: "+str(e.attrib))
        for density in options[setting.DENSITY]:
            config={k:v[0] for k,v in options.items()}
            config[setting.DENSITY]=density
            for system in ("nds","arcadetate","gba"):
                values=resolve_settings(root,config,system)
                lines=2 if system in ("nds","arcadetate") else 1
                require(int(values["cardTitleLines"])==lines and values["cardTitleWrap"]==str(lines==2).lower(),
                        "portrait card captions must have two lines")
        assets=set()
        for look,density,video,art,motion in itertools.product(*options.values()):
            selected=dict(zip(options,(look,density,video,art,motion)))
            values=resolve_settings(root,selected,"pico8")
            gba=resolve_settings(root,selected,"gba")
            for system,mode in (("arcadetate","minSize"),("vertical","screen"),("vectrex","screen")):
                require(resolve_settings(root,selected,system)["u36.card15"]==mode,"incorrect portrait fit for "+system)
            cols,rows=map(int,gba["u36.card18"].split())
            if density=="grandes":
                height=(round(float(gba["u36.card17"].split()[1])*480)-16-(rows-1)*7)/rows
                require(cols==2 and height=={"iris":141,"ambar":128}[look],"GBA reference grid dimensions")
            else:
                require(cols==3,"GBA compact setting")
            require(values["look"]==look,"style not applied")
            notice=root.find("view[@name='screen']/notification[@name='notification']")
            meter=root.find("view[@name='screen']/notification[@name='meters']")
            require(notice.findtext("backgroundColor")=="${accent}" and notice.findtext("color")=="${ctaInk}"
                    and notice.findtext("iconPath").endswith("/notice.png") and meter.findtext("vertical")=="true",
                    "independent high-contrast toast and vertical meters")
            require(all(meter.findtext(tag)==token for tag,token in
                        (("backgroundColor","${accent}"),("color","${ctaInk}"),("fillColor","${ctaInk}"),
                         ("trackColor","${meterTrack}"),("trackBorderColor","${ctaInk}"),("borderColor","${ctaInk}"))),"meter colors disconnected")
            def luminance(token):
                rgb=bytes.fromhex(values[token])
                require(len(rgb)==3,"opaque meter palette required")
                channels=[v/255 for v in rgb]
                return sum(k*(v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4)
                           for k,v in zip((.2126,.7152,.0722),channels))
            surface,empty,ink=(luminance(k)+.05 for k in ("accent","meterTrack","ctaInk"))
            require(surface/ink>=7 and empty/ink>=15,"insufficient vertical meter contrast")
            require(values["videoDelay"]==("-1" if video=="no" else "450"),"video switch disconnected")
            require(values["u36.card18"].split()[0]=="3","PICO-8 needs three columns")
            require(values["animateSystems"]==("0" if motion=="fijas" else "1"),"motion switch disconnected")
            require(values["detailPrimary"]==("image" if art=="captura" else "thumbnail"),"preferred art disconnected")
            for e in root.iter():
                val=e.text or ""
                for var in re.findall(r"\$\{([^}]+)\}",val):
                    require(var in values,"undefined variable: "+var)
                    val=val.replace("${"+var+"}",values[var])
                assets.update(re.findall(r'es-theme-canica/[a-zA-Z0-9./_-]+\.(?:png|ttf)',val))
        for asset in assets:require(asset in names,"missing packaged resource: "+asset)
        for name in names:
            if name.endswith(".png"): require(z.read(name).startswith(b"\x89PNG\r\n\x1a\n"),"invalid image")
        require(all("es-theme-canica/fonts/"+f in names for f in ("OFL.txt","D-DIN-OFL.txt","D-DINCondensed-Bold.ttf")),"title font or license missing")
        require(all(name in names for name in LICENSES),"theme license missing")
        # A stale option or first launch must select a complete baseline.
        defaults={n.tag:n.text for b in root.findall("variables") if not b.attrib for n in b}
        require(defaults["look"]=="iris" and defaults["u36.card18"] and defaults["videoDelay"]=="450","unsafe default")
        for node in ("gamegrid","identityName","saveLabel","detailHeartoff","detailStars0","description","menuText","meters"):
            require(any(e.get("name","").lower()==node.lower() for e in root.iter()),"missing native component: "+node)
        grid=root.find("view[@name='grid']")
        tile=grid.find("gridtile[@name='default']")
        for count in range(6):
            detail=grid.find(f"image[@name='detailStars{count}']")
            card=tile.find(f"image[@name='cardStars{count}']")
            require(detail.findtext("path").endswith(f"/stars-{count}.png"),"wrong detail rating strip")
            if count:
                require(card.findtext("path")==detail.findtext("path") and card.findtext("visible")==detail.findtext("visible"),
                        "different ratings between tile and details")
            else:
                require(card is None,"unrated tile shows stars")
        shade=tile.find("image[@name='badgeShade']")
        require(shade.findtext("path").endswith("/badge-fade.png") and "game:rating" not in shade.findtext("visible")
                and tile.find("image[@name='savedPill']") is None,"shared top gradient")
        for v in root.findall("variables"):
            if v.find("cardStarsSize") is None:continue
            cols,rows=map(int,v.findtext("u36.card18").split())
            grid_w,grid_h=map(float,v.findtext("u36.card17").split())
            w=(640*grid_w-16-7*(cols-1))/cols
            h=(480*grid_h-16-7*(rows-1))/rows
            def local(tag):
                x,y=map(float,v.findtext(tag).split())
                return round(x*w),round(y*h)
            x,y=local("cardStarsPos")
            sw,sh=local("cardStarsSize")
            hx,hy=local("cardHeartPos")
            sx,sy=local("savedPos")
            mw,mh=local("badgeMark")
            compact=v.get("ifSubset")==f"{setting.DENSITY}:compacta"
            require(mw==mh==(13 if compact else 17) and sw==5*sh and (9<=sh<=11 if compact else sh==14)
                    and x+sw+2<=sx and sx+mw+2<=hx and abs(w-hx-mw-x)<1 and sy==hy
                    and abs((y+sh/2)-(hy+mh/2))<=1 and local("badgeShadeSize")[0]==round(w),
                    "card marker size, spacing, order or gradient extent")
        splash=ET.fromstring(z.read("es-theme-canica/gamesplash.xml")).find("view[@name='splash']")
        require(defaults["esGameLaunchTransition"]=="shortFade" and splash is not None
                and splash.findtext("splash[@name='splash']/backgroundColor")=="000000FF"
                and all(splash.findtext(node+"/visible")=="false" for node in ("image[@name='background']", "text[@name='label']")),
                "game launch must fade in place without a second cover or title")
        require(defaults["esGameListXAction"]=="savestates" and "favAction" not in raw,"incorrect X action")
        require(grid.findtext("imagegrid[@name='gamegrid']/animateSelection")=="false","moving game selection background")
        focus=tile.find("ninepatch[@name='selection']")
        require(all(n.get("duration")=="0" for n in focus.findall("storyboard/animation")),"lagging game focus")
        def pixels(position):
            x,y=map(float,position.split())
            return round(x*640),round(y*480)
        def pos(node):
            return pixels(node.findtext("pos"))
        keys=[grid.find(f"image[@name='button{k}']") for k in ("L1","R1","L2","R2")]
        require(len({pos(n)[1] for n in keys})==1,"shoulder alignment")
        systems=root.find("view[@name='system']")
        still=systems.find("image[@name='lastPicture']")
        video=systems.find("video[@name='lastVideo']")
        require("${stillSystems}" in still.findtext("visible") and "${animateSystems}" in video.findtext("visible")
                and still.findtext("path")==video.findtext("snapshot") and
                all(video.findtext(flag)=="true" for flag in ("showSnapshotDelay","showSnapshotNoVideo","exclusiveSnapshot"))
                and grid.findtext("video[@name='gridtile.video']/exclusiveSnapshot")=="true","exclusive preview and still fallback")
        for suffix,tint in (("Dmg","C9E23CFF"),("Mono","F2EAD8FF")):
            for tag,base in (("image","lastPicture"),("video","lastVideo")):
                comp=systems.find(f"{tag}[@name='{base}{suffix}']")
                require(comp.findtext("color")==tint and comp.findtext("saturation")=="0","missing monochrome preview profile")
        shoulders=keys+[systems.find(f"image[@name='button{k}']") for k in ("L1","R1")]
        require(all(pixels(n.findtext("size"))==(26,18) for n in shoulders),"inconsistent shoulder glyphs")
        require(tile.find("text[@name='gameSystem']") is None and
                "game:system:theme" in grid.findtext("image[@name='identityLogo']/path"),"collection console label")
        saved=tile.find("image[@name='savedSlot']")
        def playback(n):
            return [n.find(f"storyboard[@event='{event}']/animation").attrib for event in ("videoplaying","videostopped")]
        heart=tile.find("image[@name='cardFavoriteon']")
        detail_saved=grid.find("image[@name='detailSaved']")
        require(saved.findtext("path")==detail_saved.findtext("path") and saved.findtext("path").endswith("/save-mark.png")
                and saved.findtext("visible")==detail_saved.findtext("visible") and "game:hasSaveState" in saved.findtext("visible")
                and playback(saved)==playback(heart)==playback(tile.find("image[@name='cardStars4']"))
                and playback(shade)[0]["to"]=="0.12","save badge lifecycle")
        for i in range(7):
            focus=systems.find(f"image[@name='tabFocus{i}']")
            icon=systems.find(f"image[@name='tabGlyph{i}']")
            icon_width=pixels(icon.findtext("maxSize"))[0]
            icon_left=pos(icon)[0]-icon_width//2
            require(icon_left-(pos(focus)[0]+3)>=8, "category marker touches the icon")
            for label in (f"tab{i}",f"tabSubtitle{i}"):
                node=systems.find(f"text[@name='{label}']")
                left=pos(node)[0]
                require(left-(icon_left+icon_width)>=6 and left+pixels(node.findtext("size"))[0]<=190,
                        "category label needs space on both sides")
        for prefix in ("tabGlyph","titleGlyph","prevTab","nextTab"):
            for i in range(7):
                icon=systems.find(f"image[@name='{prefix}{i}']")
                size=pixels(icon.findtext("maxSize"))[0]
                require(icon.findtext("default").endswith(f"-{size}.png") and icon.findtext("linearSmooth")=="false",
                        "category artwork must match its native resolution")
        title=grid.find("text[@name='gameName']")
        require(title.findtext("text")=="{game:name}" and title.findtext("autoScroll")=="vertical"
                and title.findtext("forceUppercase")=="false" and not title.findtext("maxLines") and pixels(title.findtext("size"))[1]==43 and title.findtext("fontPath").endswith("/D-DINCondensed-Bold.ttf"),"scroll complete title")
        require(defaults.get("esSingleNewGame")=="true" and defaults.get("esSearchTitle")=="Buscar juegos",
                "save and search entry points")
        for name in ("searchKeys","searchActions"):
            skin=root.find(f".//menuKeyboard[@name='{name}']")
            require(skin is not None and skin.findtext("focusedPath")!=skin.findtext("path"), "distinct search key focus")
        require(all(defaults.get(k) for k in ("esWordComplete","esWordStart","esWordNext","esWordEmpty","esNoPickControls"))
                and all(k in defaults["esSearchShortcuts"] for k in ("L2","R2","START"))
                and "Insertar" in defaults["esWordControls"], "word completion card controls")
        library_fields=("total","favorites","gamesPlayed")
        require(all(defaults.get(k) for k in ("esSaveToday","esSaveYesterday","esSaveUnknownDate")), "missing save date labels")
        for panel in (grid,systems):
            require(panel.findtext("text[@name='stattotal']/text")=="tostring({system:visibleGameCount})"
                    and "{system:libraryGameCount}" in panel.findtext("text[@name='statLabeltotal']/text"),
                    "separate the visible game count and library total")
            for field in library_fields:
                require(not panel.findtext(f"text[@name='stat{field}']/autoScroll"), "library counters must stay stationary")
        for marker in grid.findall("image"):
            if marker.get("name","").startswith("statIcontotal"):
                require("{system:visibleGameCount}" in marker.findtext("visible"), "icon must follow numeric search results")

        for panel,left,title,fields,source in ((grid,0,"gameName",("Plays","Time","Players"),"{game:"),
                                              (systems,640,"identityName",library_fields,"{system:")):
            heading=panel.find(f"text[@name='{title}']")
            title_bottom=pos(heading)[1]+pixels(heading.findtext("size"))[1]
            for i,field in enumerate(fields):
                icon=panel.find(f"image[@name='statIcon{field}']")
                value=panel.find(f"text[@name='stat{field}']")
                caption=panel.find(f"text[@name='statLabel{field}']")
                require(value is not None and source in value.findtext("text"),"counter must belong to the selected entity")
                require((field=="Time" or pos(value)[0]-pos(icon)[0]==18) and pixels(icon.findtext("size"))==(15,15)
                        and pos(caption)[1]==pos(value)[1]+17 and caption.findtext("alignment")=="center"
                        and pos(icon)[1]==pos(value)[1]+1, "detail counter geometry")
                if field=="Time":
                    vw=pixels(value.findtext("size"))[0]
                    center=pos(caption)[0]-1+pixels(caption.findtext("size"))[0]/2
                    require(vw>=65 and abs(pos(value)[0]+vw/2-center-9)<=1 and value.findtext("alignment")=="center"
                            and "{game:gametime}" in icon.findtext("visible") and len([i for i in panel.findall("image") if i.get("name","").startswith("statIconTime")])>1
                            and pos(value)[0]+vw+3<=pos(panel.find("image[@name='statIconPlayers']"))[0],
                            "center the time run and reserve a gutter before players")
        for field in library_fields:
            value=grid.find(f"text[@name='stat{field}']")
            require(pos(value)[0]>200 and 31<=pos(value)[1]<50 and "{system:" in value.findtext("text"),
                    "system totals belong in the game list navigation row")
            icon=grid.find(f"image[@name='statIcon{field}']")
            require(pixels(icon.findtext("size"))==(15,15) and value.findtext("alignment")=="center"
                    and grid.find(f"image[@name='statIcon{field}4']") is not None,
                    "library pictograms in the shoulder row")
        for name,unit in (("Time","s"),("TimeMinutes","m"),("TimeHours","h"),("TimeHoursMinutes","m")):
            clock=grid.find(f"text[@name='stat{name}']")
            require(clock is not None and clock.findtext("text").endswith('"'+unit+'"') and
                    pos(clock)==pos(grid.find("text[@name='statTimeMissing']")),"compact time slots")
        require(grid.find("text[@name='maker']") is None and "empty({game:desc})" in grid.findtext("text[@name='description']/visible"),
                "redundant console identity or empty description")
        for look in options[setting.STYLE]:
            selected={k:values[0] for k,values in options.items()}
            selected[setting.STYLE]=look
            settings=resolve_settings(root,selected,"gba")
            action=pos(grid.find("image[@name='saveAction']"))[1]
            for vw,prefix,left,suffix in ((grid,"save",0,""),(grid,"save",0,"InGame"),(systems,"resume",640,""),(systems,"resume",640,"Suggested")):
                face=vw.find(f"image[@name='{prefix}Key{suffix}']")
                label=vw.find(f"text[@name='{prefix}Label{suffix}']")
                label_start=pos(label)[0]
                label_end=label_start+pixels(label.findtext("size"))[0]
                require(label_end==left+180 and abs(label_start-pos(face)[0]-21)<=1
                        and pixels(face.findtext("size"))==(16,16) and label_start<left+100
                        and face.findtext("visible")==label.findtext("visible"),
                        "keep the X and label together with room for the native text renderer")
            counters=pos(grid.find("text[@name='statLabelPlays']"))[1]
            marks=pos(grid.find("image[@name='detailHeartoff']"))[1]
            last=pos(grid.find("text[@name='lastValue']"))[1]
            studio=pos(grid.find("text[@name='gameStudio']"))[1]
            title=grid.find("text[@name='gameName']")
            start=pos(grid.find("image[@name='statIconPlays']"))[1]
            art=grid.find("image[@name='art']")
            genre=grid.find("text[@name='genre']")
            genre_y=pos(genre)[1]
            art_width,art_height=pixels(art.findtext("maxSize"))
            art_top=pos(art)[1]-art_height/2
            for state in ("on","off"):
                heart=grid.find("image[@name='detailHeart"+state+"']")
                require(pos(heart)==(169,63) and pixels(heart.findtext("size"))==(17,17),"right favourite moved")
            require(pos(detail_saved)==(148,marks),"right save position")
            for count in range(6):
                stars=grid.find(f"image[@name='detailStars{count}']")
                require(pos(stars)==(14,marks) and pixels(stars.findtext("size"))==(80,16)
                        and marks+16<=art_top,"left ranking geometry")
            require((art_width,art_height)==(172,127) and art_top+art_height<=pos(title)[1]+1
                    and pos(genre)[0]<=34 and pixels(genre.findtext("size"))[0]>=150
                    and -3<=genre_y-pos(title)[1]-pixels(title.findtext("size"))[1]<=6
                    and genre_y<start<counters<studio<last<action and last-studio<=19
                    and action<pos(grid.find("text[@name='description']"))[1],"box overlay and game details order")
        require(len([n for n in systems.findall("text") if n.get("name","").startswith("tabSubtitle")])==7,
                "category subtitles missing")
        menu=root.find("view[@name='menu']")
        for widget in ("menuButton","menuGroup","menuPrompt","menuIcons","menuSwitch","menuSlider","menuTile",
                       "menuTextEdit","menuKeyboard","menuScreenSaver"):
            require(menu.find(widget) is not None,"missing native menu component "+widget)
        require(menu.findtext("menuText[@name='menutext']/selectorPath") and
                menu.findtext("menuText[@name='menufooter']/atBottom")=="true","unframed menu or displaced footer")
        apps=tile.find("image[@name='appSymbol']")
        require(apps is not None and apps.findtext("default") and "utility-icons/" in apps.findtext("path"),
                "missing standalone or custom utility icon")
        sidebar=systems.find("image[@name='u38AppIcon0']")
        require(sidebar.findtext("path").replace("system:recent1:","game:")==apps.findtext("path"),"utility symbols differ between views")
        from utility_art import EXTRAS, STOCK_TOOLS, SYMBOLS
        for look in options[setting.STYLE]:
            base="es-theme-canica/art/"+look+"/"
            for theme,symbol,_ in EXTRAS:
                require(base+"extra-"+theme+".png" in names and
                        systems.find(".//image[@name='extraSymbol"+symbol+"']") is not None,"empty Extras card")
            for symbol in SYMBOLS:
                require(base+"symbol-"+symbol+".png" in names,"utility glyph missing")
            for label,symbol in STOCK_TOOLS.items():
                require(z.read(base+"tools/"+label+".png")==z.read(base+"symbol-"+symbol+".png"),"stock utility glyph mismatch")
        for child in tile:
            if child.get("name","").startswith(("app","selection")):
                continue
            if child.tag in ("image","text"):
                require(child.find("storyboard[@event='videoplaying']/animation") is not None and
                        child.find("storyboard[@event='videostopped']/animation").get("to")=="1","preview overlay lifecycle")
        console_tile=systems.find("imagegrid/itemTemplate")
        card=console_tile.find("image[@name='localIllustration']")
        require("cards/" in card.findtext("visible") and "${" not in card.findtext("visible").replace("${decorations}",""),
                "both looks must use the same local console card")
        require(console_tile.findtext("image[@name='wordmark']/pos")==".055 .046" and
                console_tile.findtext("image[@name='consoleHardware']/origin")=="1 1" and
                console_tile.findtext("image[@name='catalogYear']/pos")==".051 .805" and
                "logos-color/" not in raw,"shared console card layout and light detail logos")
        require(defaults["decorations"] == "/userdata/decorations/canica", "wrong default decoration path")
        for panel in (systems,grid):
            brand = panel.find("image[@name='brandMark']")
            title = panel.find("text[@name='library']")
            require(title.findtext("text") == "CANICA" and title.findtext("visible") == brand.findtext("visible"),
                    "theme name and mark must switch together")
            play=panel.find("image[@name='resumePlay']")
            require(play.findtext("path").endswith("/resume-play.png") and
                    play.findtext("visible")==panel.findtext("image[@name='chord']/visible"),"resume play indicator")
        require(defaults["esRandomCollectionPreview"]=="true" and "collectionArt" not in raw and
                "{system:continue:image}" in still.findtext("path") and all(n.findtext("path") == "("+n.findtext("visible")+") ? {system:continue:video} : ''"
                    for n in systems.findall("video") if n.get("name","").startswith("lastVideo")) and
                defaults["esRotateCollectionPreview"]=="true" and defaults["esRotateConsolePreview"]=="true" and
                "{system:previewIsLatest}" in systems.findtext("text[@name='lastLabel']/text") and
                defaults["systemtabs"].startswith("EXTRAS=recent,all,favorites,") and
                "${previewHeading}" in systems.findtext("text[@name='lastLabel']/text") and
                "{system:continue:lastplayedDays}" in systems.findtext("text[@name='lastWhen']/visible"),
                "collection panel must use the shared selected game")
        platform=systems.find("text[@name='lastPlatform']")
        require(platform.findtext("text")=="{system:continue:system:fullName}" and
                platform.findtext("autoScroll")=="horizontal" and "${showPreviewPlatform}" in platform.findtext("visible") and
                pos(platform)[1]+pixels(platform.findtext("size"))[1]<=215 and defaults["showPreviewPlatform"]=="0",
                "source console must fit above the selected game image")
        headings={v.get("if"):v.findtext("previewHeading") for v in root.findall("variables")
                  if v.get("if") and v.findtext("showPreviewPlatform")=="1" and v.find("previewHeading") is not None}
        for collection,title in (("recent","ÚLTIMOS JUGADOS"),("all","DE TU BIBLIOTECA"),("favorites","SUGERENCIAS DEL CHEF")):
            require(headings.get("{system.name} == '"+collection+"'")==title,"incorrect collection heading")
        print(f"{len(names)} files, {len(assets)} resolved resources, 32 configurations, PICO-8, GBA reference geometry and safe defaults")
    print(hashlib.sha256(path.read_bytes()).hexdigest())


if __name__=="__main__":
    validate(Path(sys.argv[1]))
