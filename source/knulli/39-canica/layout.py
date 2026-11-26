"""Canica screens in design pixels. The grid and controls use ES's native bindings."""
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from utility_art import EXTRAS

HERE = Path(__file__).resolve().parent
KNULLI = HERE.parent
HOME = KNULLI / "37-home-redesign/install/files/home"
COL = KNULLI / "38-column-home/install/files/columns"
RED = KNULLI / "36-theme-redesign/install/files/redesign"
CAT = json.loads((KNULLI / "37-home-redesign/tools/home.json").read_text())
ROOT = "${themePath}"
ART = ROOT + "/art/"
LOOK = ART + "${look}/"
FONT = ROOT + "/fonts/Roboto-"
DISPLAY_FONT = ROOT + "/fonts/D-DINCondensed-Bold.ttf"
MONO_FONT = ROOT + "/fonts/IBMPlexMono-Medium.otf"
UTILS = ("tools", "emulators", "imageviewer")
UTILITY = " || ".join("{system.name} == '" + name + "'" for name in UTILS)
GAMES = "!({system:theme} == 'tools' || {system:theme} == 'emulators' || {system:theme} == 'imageviewer')"
PERSONAL = "${decorations}/"
# The kit's version as the menu shows it; build.py sets it from its VERSION.
KIT = {"label": ""}


def logo_file(source):
    """A system's logo: the owner's own PNG, else the one the kit carries."""
    return 'firstfile("'+PERSONAL+'logos/" + '+source+' + ".png", "'+ART+'logos/" + '+source+' + ".png", "")'


def logo_exists(source):
    return '(exists("'+PERSONAL+'logos/" + '+source+' + ".png") || exists("'+ART+'logos/" + '+source+' + ".png"))'
# One category image follows its label through the library and both shoulder hints.
CATEGORY_ICONS = ("extras", "eight-bit", "sixteen-bit", "thirty-two-bit", "handheld", "arcade", "computer")
PORTABLE_DESCRIPTIONS = {
    "tools":"Herramientas disponibles en esta instalación.",
    "imageviewer":"Capturas guardadas en esta consola.",
    "emulators":"Emuladores disponibles en esta instalación.",
    "recent":"Los juegos que abriste, del más reciente al más antiguo.",
    "continue":"Tus últimos quince juegos, cada uno donde lo dejaste.",
    "all":"Juegos de todos tus sistemas en una sola lista.",
    "mame":"Juegos de máquinas recreativas compatibles con MAME.",
    "arcade":"Juegos de máquinas recreativas de distintos fabricantes.",
    "dos":"Juegos para MS-DOS y computadoras compatibles con IBM PC.",
    "favorites":"Los juegos que marcaste como favoritos en todas tus consolas.",
}


def prop(node, key, value):
    ET.SubElement(node,key).text=str(value)


def element(parent, tag, name, properties=None, extra=True, **attrs):
    n=ET.SubElement(parent,tag,{"name":name, **({"extra":"true"} if extra else {}), **attrs})
    for k,v in (properties or {}).items():
        prop(n,k,v)
    return n


def norm(x,y,w=640,h=480):
    return f"{x/w:.6f} {y/h:.6f}"


def image(v,name,x,y,w,h,path,*,z=30,show=None,contain=False):
    dims=({"pos":norm(x+w/2,y+h/2),"origin":"0.5 0.5","maxSize":norm(w,h)}
          if contain else {"pos":norm(x,y),"size":norm(w,h)})
    return element(v,"image",name,{**dims,"path":path,"linearSmooth":"true","zIndex":z,
                                   **({"visible":show} if show else {})})


def font_size(px):
    # KNULLI truncates the requested pixel size before applying its 640×480 font scale.
    native = min(range(3, 40), key=lambda n: (abs(int(n * 1.31) - px), -n))
    return f"{(native + .25) / 480:.6f}"


def text(v,name,x,y,w,h,value,px=12,*,color="${ink}",align="left",weight="SemiBold",show=None,wrap=False,scroll=False,z=31):
    n=element(v,"text",name,{"pos":norm(x,y),"size":norm(w,h),"text":value,"fontSize":font_size(px),
              "fontPath":FONT+weight+".ttf","color":color,"alignment":align,"verticalAlignment":"top" if wrap else "center",
              "multiLine":str(wrap).lower(),"zIndex":z})
    if wrap:prop(n,"lineSpacing","1.13")
    if show:prop(n,"visible",show)
    if scroll:prop(n,"autoScroll","vertical" if wrap else "horizontal")
    return n


def view(root,name,condition=None):
    return ET.SubElement(root,"view",{"name":name,**({"if":condition} if condition else {})})


def key(v,k,x,y,show=None,idx=""):
    shoulder=len(k)>1
    if shoulder:
        return image(v,"button"+k+idx,x+2,y+2,26,18,ART+k.lower()+".png",show=show,z=74)
    return image(v,"button"+k+idx,x,y,17,17,LOOK+k.lower()+".png",show=show,z=74)


def ring(n, duration=100):
    frame=element(n,"ninepatch","selection",{"pos":"0 0","size":"1 1","path":LOOK+"focus.png",
                  "cornerSize":"${frameCorner}","opacity":"0","zIndex":"75"})
    for event,value in (("activate","1"),("deactivate","0"),("unfocus","0")):
        story=ET.SubElement(frame,"storyboard",event=event)
        ET.SubElement(story,"animation",property="opacity",to=value,duration=str(duration),mode="linear")


def variables(parent, values, **attrs):
    block=ET.SubElement(parent,"variables",attrs)
    for k,v in values.items():prop(block,k,v)


def option(root,key,label,choices):
    subset=ET.SubElement(root,"subset",name=key,displayName=label)
    for k,v in choices:
        ET.SubElement(subset,"include",name=k,displayName=v)


def system_data(root):
    data={**{k:v for k,v in CAT["grouped"].items() if isinstance(v,dict)},**CAT["systems"]}
    tabs=[]
    for tab in CAT["tabs"]:
        systems=tab["systems"]
        if tab["name"]=="EXTRAS":
            # The game switcher first, then the recent games
            systems=["continue","recent"]+[system for system in systems if system not in ("continue","recent")]
        tabs.append(tab["name"]+"="+",".join(systems))
    if not tabs[-1].endswith(",*"):tabs[-1]+=",*"
    variables(root,{"systemtabs":";".join(tabs),"esColumnPan":"0.3125","esColumnSlide":"0.6875",
              "esColumnHeader":str(31/480),"esConsoleCycleSkipTab":"EXTRAS","esResumeChordMarker":"/var/run/canica/resume.enabled",
              "esSingleNewGame":"true","esSearchTitle":"Buscar juegos","esSearchHint":"Título del juego",
              "esSearchClear":"Limpiar","esSearchSubmit":"Buscar",
              "esWordComplete":"Completar palabra","esWordStart":"Palabras frecuentes",
              "esWordNext":"Siguiente palabra","esWordEmpty":"Sin sugerencias de palabra",
              "esNoPickControls":"L1  Borrar letra     ·     X  Limpiar     ·     B  Volver     ·     START  Buscar",
              "esWordControls":"← →  Elegir palabra     ·     A  Insertar     ·     B  Teclado     ·     START  Buscar",
              "esSearchShortcuts":"L2  Completar     ·     R2  Elegir     ·     L1  Borrar     ·     X  Limpiar     ·     B  Volver     ·     START  Buscar",
              "esSaveToday":"Hoy","esSaveYesterday":"Ayer","esSaveUnknownDate":"Sin fecha",
              "esCardScreenshotDirectory":"/userdata/decorations/canica-capturas/juegos","esGameListXAction":"savestates","esGameLaunchTransition":"shortFade","esRandomCollectionPreview":"true","esRotateCollectionPreview":"true","esRotateConsolePreview":"true",
              "previewHeadingPos":norm(653,190),"showPreviewPlatform":"0",
              "previewHeading":"",
              "esNoSaveStatesText":"Partidas\n\nEste emulador no ofrece estados rápidos en este menú. Si el juego guarda progreso, puedes cargarlo desde el propio juego.",
              "esRenderOnChange":"true","esBindShownOnly":"true","esIdlePause":"60","sysDesc":"","sysLabel":"{system:fullName}"})
    variables(root,{"sysDesc":PORTABLE_DESCRIPTIONS["continue"],"sysLabel":"Continuar"},**{"if":"{system.name} == 'continue'"})
    for system,heading in (("continue","CONTINUAR"),("recent","ÚLTIMOS JUGADOS"),("all","DE TU BIBLIOTECA"),("favorites","SUGERENCIAS DEL CHEF")):
        variables(root,{"previewHeading":heading,"previewHeadingPos":norm(653,178),"showPreviewPlatform":"1"},**{"if":"{system.name} == '"+system+"'"})
    for k,d in data.items():
        desc=PORTABLE_DESCRIPTIONS.get(k,d.get("desc",""))
        variables(root,{"sysDesc":desc,
                       "sysLabel":d.get("label") or "{system:fullName}"},**{"if":"{system.name} == '"+k+"'"})


def utility_icon(item):
    override='"'+PERSONAL+'utility-icons/${look}/" + stem({'+item+':image}) + ".png"'
    bundled='"'+LOOK+'tools/" + {'+item+':name} + ".png"'
    return 'firstfile('+override+', '+bundled+', "'+LOOK+'symbol-tool.png")'


def tool_overview(v):
    reference=ET.parse(COL/"columns.xml").find(".//view[@name='system']")
    for n in reference:
        name=n.get("name","")
        if not name.startswith(("u38UtilityCount","u38LibraryContents","u38App","u38Latest","u38EmptyShots")):continue
        n=deepcopy(n)
        for child in n.iter():
            if child.tag=="fontPath":child.text=FONT+"Bold.ttf"
            if child.tag=="color":child.text="${ink}"
        if name.startswith("u38AppIcon"):
            item="system:recent"+str(int(name.removeprefix("u38AppIcon"))+1)
            n.find("path").text=utility_icon(item)
            prop(n,"default",LOOK+"symbol-tool.png")
            prop(n,"linearSmooth","true")
        v.append(n)


def header(v):
    image(v,"headerBand",0,0,640,31,LOOK+"top.png",z=51)
    chord='exists("/var/run/canica/resume.enabled") && !empty({global:lastPlayed:name})'
    # FN + START, then the last game: the badge is 73 px wide
    image(v,"chord",11,8,73,15,LOOK+"chord.png",show=chord,z=62)
    image(v,"resumePlay",96,9,13,13,LOOK+"resume-play.png",show=chord,z=62)
    group=element(v,"stackpanel","resumeInfo",{"pos":norm(115,7),"size":norm(304,17),
                  "orientation":"horizontal","separator":"4","visible":chord,"zIndex":62})
    for i,(name,value,weight,color) in enumerate([
        ("resumeName","{global:lastPlayed:cleanName}","Bold","${ink}"),
        ("resumeSystem",'empty({global:lastPlayed:system:fullName}) ? "" : "· " + {global:lastPlayed:system:fullName}',"Medium","${muted}")]):
        element(group,"text",name,{"size":"0 1","text":value,"fontPath":DISPLAY_FONT if i==0 else FONT+weight+".ttf",
                "fontSize":font_size(13 if i==0 else 11),"color":color,"multiLine":"false","verticalAlignment":"center","zIndex":i+1})
    brand='empty({global:lastPlayed:name}) || !exists("/var/run/canica/resume.enabled")'
    image(v,"brandMark",11,6,19,19,LOOK+"canica.png",show=brand,z=62)
    text(v,"library",35,6,172,19,"CANICA",12,color="${accent}",weight="Black",show=brand,z=62)
    key(v,"Y",441,7)
    text(v,"search",464,7,45,17,"Buscar",11,weight="Black",z=72)


def counter_cell(v, name, left, top, width, icon, value, label, show, *, inset=4, compact=False, scroll=True):
    # Reserve a stable anchor for the icon/value and center the caption under its cell.
    size=15
    x=left+inset
    image(v,"statIcon"+name,x,top+1,size,size,LOOK+"metric-"+icon+".png",show=show)
    value_x=x+size+3
    node=text(v,"stat"+name,value_x,top,width+left-value_x,18,value,14 if compact else 15,
              weight="Black",show=show,scroll=scroll)
    text(v,"statLabel"+name,left,top+17,width,13,label,10.5 if compact else 10,
         color="${muted}",align="center",show=show)
    return node


def metrics(v,x,y,show=None,compact=False):
    step=67 if compact else 62
    for i,(binding,label,icon,inset) in enumerate((("total","juegos","games",5),("favorites","favs","favs",10),
                                                   ("gamesPlayed","jugados","played",9))):
        left=x+i*step
        count="{system:visibleGameCount}" if binding=="total" else "{system:"+binding+"}"
        if binding=="total":
            total="{system:libraryGameCount}"
            label=(count+" == "+total+' ? "juegos" : "de " + tostring('+total+')')
        value=counter_cell(v,binding,left,y,step,icon,"tostring("+count+")",label,show,
                           inset=inset,compact=compact,scroll=False)
        if compact:
            # The caption stays on the cell center. Tabular Roboto digits take 8 px at this size.
            # Center the number half an icon+gap to the right; its icon follows the leading digit.
            value.find("pos").text=norm(left+18,y)
            value.find("size").text=norm(step-18,18)
            value.find("alignment").text="center"
            base=v.find("image[@name='statIcon"+binding+"']")
            for digits in range(1,7):
                marker=base if digits==1 else deepcopy(base)
                if digits>1:
                    marker.set("name","statIcon"+binding+str(digits))
                    v.append(marker)
                limits=[]
                if digits>1:limits.append(count+" >= "+str(10**(digits-1)))
                if digits<6:limits.append(count+" < "+str(10**digits))
                marker.find("visible").text="("+show+") && ("+" && ".join(limits)+")"
                marker.find("pos").text=norm(round(left+(step-18-8*digits)/2)-1,y+1)



def cta(v,prefix,panel,y,show,choices,key_art="cta-x.png"):
    image(v,prefix+"Action",panel+13,y,174,31,LOOK+"cta.png",show=show)
    for suffix,label,predicate in choices:
        visible="("+show+") && ("+predicate+")"
        width=category_label_width(label,"ExtraBold",13)
        x=panel+100-(16+5+width)/2
        image(v,prefix+"Key"+suffix,x,y+7.5,16,16,LOOK+key_art,show=visible,z=33)
        text(v,prefix+"Label"+suffix,x+21,y,panel+180-(x+21),31,label,13,weight="ExtraBold",
             color="${ctaInk}",show=visible,z=33)


def identity(v,panel,context=False,show=None):
    # The faceplate occupies the same 200-pixel column on either side of the library.
    source="({system:collection} ? {game:system:theme} : {system:theme})" if context else "{system:theme}"
    name="{system:collection} ? {game:system:fullName} : {system:fullName}" if context else "${sysLabel}"
    path=logo_file(source)
    has=logo_exists(source)
    def visible(condition):
        return "("+show+") && ("+condition+")" if show else condition
    image(v,"identityLogo",panel+39,34,122,28,path,show=visible(has),contain=True)
    fallback=text(v,"identityName",panel+37,34,126,28,name,14,align="center",weight="Black",show=visible("!"+has),scroll=True)
    fallback.find("fontPath").text=DISPLAY_FONT


def game_title(v,prefix,x,y,w,name,show,align="top"):
    title=text(v,prefix+"Name",x,y,w,43,name,23,weight="ExtraBold",wrap=True,show=show)
    title.find("fontPath").text=DISPLAY_FONT
    prop(title,"forceUppercase","false")
    title.find("lineSpacing").text="0.94"
    title.find("verticalAlignment").text=align
    prop(title,"autoScroll","vertical")
    prop(title,"autoScrollDelay",1300)
    prop(title,"autoScrollSpeed",55)


def game_credits(v,prefix,x,y,w,dev,year,show,credit_icon=False):
    left=x
    if credit_icon:
        image(v,prefix+"CreditIcon",x,y+3,11,11,ART+"dev.png",show="("+show+") && !empty("+dev+")")
        left+=15
    text(v,prefix+"Studio",left,y,x+w-left-38,17,dev,12.5,weight="Bold",color="${ink}",show="("+show+") && !empty("+dev+")",scroll=True)
    text(v,prefix+"Year",x+w-35,y,35,17,year,12,color="${muted}",show="("+show+") && !empty("+year+")",align="right")


def category_icon(v,name,index,x,y,size,show=None):
    slug=CATEGORY_ICONS[index]
    icon=image(v,name,x,y,size,size,PERSONAL+"categories/"+str(size)+"/"+slug+".png",show=show,contain=True)
    prop(icon,"default",ART+f"category-{slug}-{size}.png")
    icon.find("linearSmooth").text="false"
    return icon


def category_label_width(name,weight,px):
    font=RED/"fonts"/("Roboto-"+weight+".ttf")
    return int(subprocess.check_output(["magick","-density","72","-font",str(font),"-pointsize",str(px),
                                        "label:"+name,"-format","%w","info:"],text=True))


def system_cards(v):
    grid=element(v,"imagegrid","imagegrid",{"pos":norm(200,63),"size":norm(440,416),"autoLayout":"3 3",
          "margin":"8 7","padding":"8 5 8 4","autoLayoutSelectedZoom":"1","animateSelection":"false",
          "centerSelection":"false","scrollLoop":"true","zIndex":"20"},extra=False)
    tpl=ET.SubElement(grid,"itemTemplate",replace="true")
    def tile_img(name,path,z):
        return element(tpl,"image",name,{"pos":"0 0","size":"1 1","path":path,"roundCorners":"${tileRadius}","zIndex":z})
    has_native='exists("'+PERSONAL+'cards/" + {system:theme} + ".png")'
    plain="!"+has_native
    tile_img("baseSurface",LOOK+"canvas.png",0)
    # Bound selection determines every tile's own artwork. Optional art stays local to the handheld.
    types={"handheld":["gba","gb","gbc","nds","atarilynx","wswan","wonderswan","gamegear","ngpc","wonderswancolor"],
           "arcade":["arcade","auto-verticalarcade","mame"],"tools":["tools"],"monitor":["pc","emulators","pico8"],
           "image":["imageviewer"],"grid":["auto-allgames"],"favs":["auto-favorites"],"played":["auto-lastplayed"]}
    prop(tile_img("systemCard",LOOK+"card-pad.png",1),"visible",plain)
    for name,keys in types.items():
        n=tile_img(name,LOOK+"card-"+name+".png",2)
        prop(n,"visible","("+plain+") && ("+" || ".join("{system:theme} == '"+k+"'" for k in keys)+")")
    # Prepared frames have the console's original screen proportions and a matte fitting the tile.
    frames = ['"/userdata/decorations/canica-capturas/" + {system:theme} + "/%d.png"' % i for i in range(5)]
    cached = "exists(" + frames[0] + ")"
    element(tpl,"image","preparedStill",{"pos":"0 0","size":"1 1","path":frames[0],
            "visible":"${stillSystems} && "+cached,"zIndex":"3"})
    element(tpl,"slideshow","preparedSlides",{"pos":"0 0","size":"1 1","path":(' + "\n" + ').join(frames),
            "interval":"5","duration":"0.6","transition":"fade","dots":"false","roundCorners":"${tileRadius}",
            "visible":"${animateSystems} && "+cached,"zIndex":"3"})
    element(tpl,"image","stillPreview",{"pos":"0.5 0.5","origin":"0.5 0.5","maxSize":"1 1","path":"{system:continue:image}",
            "visible":"${stillSystems} && !"+cached,"zIndex":"3"})
    element(tpl,"slideshow","captures",{"pos":"0 0","size":"1 1","path":"{system:slides}","interval":"5",
            "duration":"0.6","transition":"fade","dots":"false","roundCorners":"${tileRadius}",
            "zIndex":"3","visible":"${animateSystems} && !"+cached})
    texture = 'firstfile("' + ART + 'display/" + {system:theme} + ".png", "")'
    tile_img("displaySurface", texture, 4)
    # A game screen behind the card darkens, so the logo and the console stay legible on it
    screenshot = cached + " || !empty({system:slides}) || !empty({system:continue:image})"
    prop(tile_img("cardDim", LOOK+"card-dim.png", 4), "visible", "(" + plain + ") && (" + screenshot + ")")
    private='firstfile("'+PERSONAL+'cards/" + {system:theme} + ".png", "")'
    prop(tile_img("localIllustration",private,7),"visible",has_native)
    # Without a local card, compose the same layout from separate artwork for both palettes.
    has_logo=logo_exists("{system:theme}")
    prop(tile_img("cardWash",LOOK+"card-wash.png",5),"visible","${cardWash}")
    hardware='firstfile("'+PERSONAL+'hardware/" + {system:theme} + ".png", "")'
    element(tpl,"image","consoleHardware",{"pos":".965 .963","origin":"1 1","maxSize":".49 .49",
            "path":hardware,"linearSmooth":"true","visible":plain,"zIndex":8})
    element(tpl,"image","wordmark",{"pos":".055 .046","origin":"0 0","maxSize":".89 .17",
            "path":logo_file("{system:theme}"),
            "visible":plain,"linearSmooth":"true","zIndex":8})
    has_year="("+plain+") && !empty({system:releaseYear})"
    element(tpl,"image","yearPlate",{"pos":".051 .805","size":".29 .14","path":LOOK+"year.png","visible":has_year,"zIndex":8})
    element(tpl,"text","year",{"pos":".051 .805","size":".29 .14","text":"{system:releaseYear}",
            "fontPath":FONT+"Bold.ttf","color":"ffdb9e","alignment":"center","verticalAlignment":"center",
            "fontSize":font_size(10.5),"visible":has_year,"zIndex":9})
    year_image='firstfile("'+ART+'years/" + {system:theme} + ".png", "")'
    element(tpl,"image","catalogYear",{"pos":".051 .805","size":".29 .14","path":year_image,
            "visible":"("+plain+") && empty({system:releaseYear})","zIndex":8})
    fallback_title="("+plain+") && !"+has_logo

    element(tpl,"image","shade",{"pos":"0 0.50","size":"1 .5","path":ART+"shade.png","visible":plain,"zIndex":5})
    element(tpl,"text","tileName",{"pos":".055 .042","size":".89 .26","text":"{system:fullName}","color":"ffffff",
          "alignment":"left","verticalAlignment":"top","fontPath":FONT+"Black.ttf","fontSize":font_size(12),
          "glowColor":"050811ff","glowSize":"1","multiLine":"true","maxLines":"2","visible":fallback_title,"zIndex":6})
    for theme,symbol,title in EXTRAS:
        show="{system:theme} == '"+theme+"'"
        prop(tile_img("extraSurface"+symbol,LOOK+"extra-"+theme+".png",12),"visible",show)
        element(tpl,"image","extraSymbol"+symbol,{"pos":".5 .36","origin":".5 .5","maxSize":".47 .47",
                "path":LOOK+"symbol-"+symbol+".png","linearSmooth":"true","visible":show,"zIndex":13})
        element(tpl,"text","extraTitle"+symbol,{"pos":".045 .64","size":".91 .31","text":title,
                "fontPath":FONT+"ExtraBold.ttf","fontSize":font_size(14),"color":"${ink}","alignment":"center",
                "verticalAlignment":"center","multiLine":"true","lineSpacing":"1.0","maxLines":"2","visible":show,"zIndex":14})
    ring(tpl)


def systems(root):
    v=view(root,"system")
    element(v,"text","systemInfo",{"visible":"false","pos":"0 1.5"},extra=False)
    image(v,"strip",0,31,840,449,LOOK+"canvas.png",z=1)
    image(v,"left",0,31,200,449,LOOK+"panel.png",z=2)
    image(v,"right",640,31,200,449,LOOK+"panel.png",z=2)
    header(v)
    text(v,"tabTitle",16,45,170,27,"Biblioteca",19,weight="Black")
    if KIT["label"]:
        text(v,"kitVersion",16,459,170,14,"Canica "+KIT["label"],10,color="${muted}",weight="Medium")
    subtitles=("Colecciones y utilidades","1977 – 1985","1987 – 1991","1994 – 1998",
               "1989 – 2004","Arcade, vertical, MAME","MS-DOS, Doom, PICO-8")
    for i,t in enumerate(CAT["tabs"]):
        y=86+i*51
        active="{system:tab} == "+str(i)
        image(v,"tabFocus"+str(i),9,y-2,182,44,LOOK+"category-selected.png",show=active)
        category_icon(v,"tabGlyph"+str(i),i,20,y+4,34)
        text(v,"tab"+str(i),60,y,129,23,t["name"],16,weight="Black")
        text(v,"tabSubtitle"+str(i),60,y+22,129,16,subtitles[i],11.5,color="${muted}")
        name=t["name"]
        title_width=category_label_width(name,"Black",16)
        left=420-(24+3+title_width)//2
        category_icon(v,"titleGlyph"+str(i),i,left,35,24,active)
        text(v,"category"+str(i),left+27,35,title_width+16,25,name,16,weight="Black",show=active)
        hint_width=category_label_width(name,"Bold",13)+3
        for role,x in (("prevTab",243),("nextTab",597-hint_width-23)):
            visible="{system:"+role+"} == '"+name+"'"
            category_icon(v,role+str(i),i,x,37,20,visible)
            text(v,role+"Label"+str(i),x+23,36,hint_width,23,name,13,weight="Bold",show=visible)
    key(v,"L1",208,37)
    key(v,"R1",602,37)
    system_cards(v)
    identity(v,640)
    metrics(v,647,73,show=GAMES)
    text(v,"consoleDescription",654,116,172,62,"${sysDesc}",12.3,color="${muted}",align="left",weight="Regular",wrap=True,scroll=True,show=GAMES)
    recent="{system:hasContinue}"
    feature="("+GAMES+") && ("+recent+")"
    resume="!{system:randomCollectionPreview} && {system:continue:lastplayedDays} >= 0"
    label='${showPreviewPlatform} ? "${previewHeading}" : ({system:previewIsLatest} ? "ÚLTIMO JUGADO" : ({system:continue:lastplayedDays} >= 0 ? "DEL HISTORIAL" : "SUGERENCIA"))'
    heading=text(v,"lastLabel",653,190,174,17,label,10.5,color="${accent}",show=feature)
    heading.find("pos").text="${previewHeadingPos}"
    show_platform="("+feature+") && ${showPreviewPlatform}"
    image(v,"lastPlatformIcon",653,198,13,13,ART+"pad.png",show=show_platform)
    text(v,"lastPlatform",670,195,157,19,"{system:continue:system:fullName}",13,
         color="${ink}",weight="SemiBold",scroll=True,show=show_platform)
    snapshot='firstfile({system:continue:image}, {system:continue:thumbnail}, "'+ART+'empty.png")'
    platform = "{system:continue:system:theme}"
    dmg = platform + " == 'gb'"
    mono = platform + " == 'wonderswan'"
    for suffix, condition, tint in (("", "!("+dmg+" || "+mono+")", None),
                                    ("Dmg", dmg, "C9E23CFF"), ("Mono", mono, "F2EAD8FF")):
        show = "("+feature+") && ("+condition+")"
        still = image(v,"lastPicture"+suffix,653,215,174,131,snapshot,
                      show="${stillSystems} && "+show,contain=True)
        moving = "${animateSystems} && "+show
        video = element(v,"video","lastVideo"+suffix,{"pos":norm(740,280.5),"origin":"0.5 0.5","maxSize":norm(174,131),
                "path":"("+moving+") ? {system:continue:video} : ''","snapshot":snapshot,
                "showSnapshotDelay":"true","showSnapshotNoVideo":"true","exclusiveSnapshot":"true",
                "visible":moving,"zIndex":32,"effect":"none","delay":"0.6"})
        if tint:
            for component in (still,video):
                prop(component,"color",tint)
                prop(component,"saturation","0")
    game_title(v,"last",653,350,174,"{system:continue:cleanName}",feature)
    game_credits(v,"last",653,397,174,"{system:continue:developer}","{system:continue:releaseyear}",feature,credit_icon=True)
    dated="("+feature+") && {system:continue:lastplayedDays} >= 0"
    when=('{system:continue:lastplayedDays} == 0 ? "Hoy · " + {system:continue:lastplayedTime} : '
          '({system:continue:lastplayedDays} == 1 ? "Ayer · " + {system:continue:lastplayedTime} : '
          'day({system:continue:lastplayed}) + "/" + month({system:continue:lastplayed}) + "/" + year({system:continue:lastplayed}))')
    image(v,"lastWhenIcon",653,416,11,11,ART+"played.png",show=dated)
    text(v,"lastWhen",668,414,159,15,when,11,color="${muted}",show=dated)
    cta(v,"resume",640,438,feature,[("","Continuar",resume),("Suggested","Jugar","!("+resume+")")])
    text(v,"emptyRecent",653,383,174,38,"Todavía no juegas nada aquí",12,color="${muted}",align="center",wrap=True,show="("+GAMES+") && !"+recent)
    tool_overview(v)
