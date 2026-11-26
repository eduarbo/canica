"""Native game grid and fixed-width metadata slots."""
from copy import deepcopy

import theme_options as setting
from layout import (ART, LOOK, FONT, DISPLAY_FONT, COL, GAMES, SCREEN_TINT, UTILITY, ET,
                    element, game_title, game_credits, identity, utility_icon, image, key, cta, counter_cell, metrics, norm, prop, ring, text, view, header, font_size)


ART_LEFT, ART_RIGHT, BADGE_Y = 14, 186, 63
GENRE_Y = 255


def card_sizes(root):
    original=ET.parse(COL/"gamelist.xml")
    blocks=original.findall("variables")
    for scale in ("grande","normal"):
        for b in blocks:
            if b.get("ifSubset")!="u38cardscale:"+scale:continue
            n=deepcopy(b)
            n.attrib.pop("ifSubset")
            if scale=="normal":n.set("ifSubset",f"{setting.DENSITY}:compacta")
            # Move the first row below the shared 31 px header and 32 px navigation.
            pos=n.find("u36.card16")
            if pos is not None:
                x,_=pos.text.split()
                pos.text=x+" "+f"{64/480:.6f}"
                peek=n.find("u36.card19")
                peek.text=str(max(0,float(peek.text)-10/480))
            root.append(n)
            if scale=="grande" and "'gba'" in n.get("if",""):
                # Two native rows plus a partly visible third. ES computes tile height
                # from the grid extent before extending the viewport by peekSize.
                for style,height in (("iris",141),("ambar",128)):
                    variant=deepcopy(n)
                    variant.set("if","{system.name} == 'gba'")
                    if style=="ambar":variant.set("ifSubset",f"{setting.STYLE}:ambar")
                    h=2*height+7+16
                    for tag,val in {"16":norm(201,64),"17":norm(433,h),"18":"2 2",
                                    "19":str((480-64-h)/480),"15":"minSize"}.items():
                        variant.find("u36.card"+tag).text=val
                    root.append(variant)
    # These recordings carry a portrait playfield inside a landscape frame.
    # Apply after both densities without changing the other portrait systems.
    tate=ET.SubElement(root,"variables",{"if":"{system.name} == 'arcadetate'"})
    prop(tate,"u36.card15","minSize")


def badges(v,card=False):
    amount="{game:rating}"
    # Keep the five levels of the catalogue's rounded percentage.
    ranges=[
        amount+" <= 0",
        amount+" > 0 && "+amount+" < 0.395",
        amount+" >= 0.395 && "+amount+" < 0.595",
        amount+" >= 0.595 && "+amount+" < 0.795",
        amount+" >= 0.795 && "+amount+" < 0.895",
        amount+" >= 0.895",
    ]
    if card:
        element(v,"image","badgeShade",{"pos":"0 0","size":"${badgeShadeSize}","path":ART+"badge-fade.png",
                                       "visible":GAMES,"zIndex":40})
    for count,predicate in enumerate(ranges):
        if card and count==0:
            continue
        show="("+GAMES+") && ("+predicate+")"
        path=ART+f"stars-{count}.png"
        if card:
            element(v,"image",f"cardStars{count}",{"pos":"${cardStarsPos}","size":"${cardStarsSize}",
                    "path":path,"linearSmooth":"true","visible":show,"zIndex":42})
        else:
            image(v,f"detailStars{count}",ART_LEFT,BADGE_Y,80,16,path,show=show)
    for state,predicate in (("off","!{game:favorite}"),("on","{game:favorite}")):
        show="("+GAMES+") && ("+predicate+")"
        path=ART+"heart-"+state+".png"
        if card:
            element(v,"image","cardFavorite"+state,{"pos":"${cardHeartPos}","size":"${badgeMark}",
                    "path":path,"visible":show,"zIndex":42})
        else:
            image(v,"detailHeart"+state,ART_RIGHT-17,BADGE_Y,17,17,ART+"detail-heart-"+state+".png",show=show)
    saved="("+GAMES+") && {game:hasSaveState}"
    if card:
        element(v,"image","savedSlot",{"pos":"${savedPos}","size":"${badgeMark}","path":ART+"save-mark.png",
                                       "linearSmooth":"true","visible":saved,"zIndex":42})
    else:
        image(v,"detailSaved",ART_RIGHT-38,BADGE_Y,17,17,ART+"save-mark.png",show=saved)


def duration_counter(v,node,left,top,width,show):
    seconds="{game:gametime}"
    minutes="(("+seconds+" / 60) >> 0)"
    hours="(("+seconds+" / 3600) >> 0)"
    remainder="("+minutes+" - "+hours+" * 60)"
    middle=left+width/2
    # Center the text half an icon-and-gap right of the cell middle. Place the clock
    # against its natural leading edge using the native Roboto Black tabular advances.
    def digits(number,ceiling):
        return [(n,f"({number} >= {10**(n-1)} && {number} < {10**n})" if n<ceiling else f"({number} >= {10**(n-1)})")
                for n in range(1,ceiling+1)]
    def widths(number,unit,ceiling):
        return [(9*n+unit,when) for n,when in digits(number,ceiling)]

    missing=seconds+" <= 0"
    formats=[
        ("",seconds+" > 0 && "+seconds+" < 60",'tostring('+seconds+') + "s"',widths(seconds,8,2)),
        ("Missing",missing,"—",[(13,missing)]),
        ("Minutes",seconds+" >= 60 && "+seconds+" < 3600",'tostring('+minutes+') + "m"',widths(minutes,13,2)),
        ("Hours",seconds+" >= 3600 && "+remainder+" == 0",'tostring('+hours+') + "h"',widths(hours,9,5)),
        ("HoursMinutes",seconds+" >= 3600 && "+remainder+" > 0",'tostring('+hours+') + "h" + tostring('+remainder+') + "m"',
         [(9*(h+m)+22,hc+" && "+mc) for h,hc in digits(hours,3) for m,mc in digits(remainder,2)]),
    ]
    available=66
    # Compensate for the caption's left side bearing at its native 10 px size.
    caption=v.find("text[@name='statLabelTime']")
    caption.find("pos").text=norm(left+1,top+17)
    node.find("pos").text=norm(middle+9-available/2,top)
    node.find("size").text=norm(available,18)
    node.find("alignment").text="center"
    bands={}
    for suffix,condition,expression,advances in formats:
        unit=deepcopy(node) if suffix else node
        unit.set("name","statTime"+suffix)
        unit.find("visible").text="("+show+") && ("+condition+")"
        unit.find("text").text=expression
        if suffix:v.append(unit)
        for advance,when in advances:
            bands.setdefault(min(available,advance),[]).append("("+condition+" && "+when+")")
    clock=v.find("image[@name='statIconTime']")
    for i,(advance,conditions) in enumerate(bands.items()):
        icon=deepcopy(clock) if i else clock
        if i:icon.set("name","statIconTime"+str(advance))
        icon.find("pos").text=norm(round(middle-(18+advance)/2),top+1)
        icon.find("visible").text="("+show+") && ("+" || ".join(conditions)+")"
        if i:v.append(icon)


def card_surface(v, size_mode):
    return element(v,"gridtile","default",{"padding":"0 0","backgroundImage":LOOK+"solid.png","backgroundCornerSize":"2 2",
                 "backgroundCenterColor":"ffffffff","backgroundEdgeColor":"ffffffff","imageColor":"ffffffff",
                 "imageSizeMode":size_mode},extra=False)


def caption_shade(tile,top=.54,show=None):
    props={"pos":f"0 {top:g}","size":f"1 {1-top:g}","path":ART+"shade.png","zIndex":30}
    if show:
        props["visible"]=show
    return element(tile,"image","captionShade",props)


def save_cards(menu):
    element(menu,"imagegrid","gamegrid",{"autoLayout":"3 1","scrollDirection":"horizontal","centerSelection":"false",
            "autoLayoutSelectedZoom":"1","animateSelection":"false","padding":"6 5 6 5","margin":"8 0",
            "gameImage":LOOK+"slot-empty.png"},extra=False)
    tile=card_surface(menu,"maxSize")
    caption_shade(tile,.43)
    ring(tile,duration=0)
    element(menu,"image","gridtile.image",{"roundCorners":"${tileRadius}","linearSmooth":"true"},extra=False)
    element(menu,"text","gridtile",{"pos":".045 .45","size":".91 .51","alignment":"left","verticalAlignment":"bottom",
            "fontPath":FONT+"Bold.ttf","fontSize":font_size(14),"color":"ffffffff","backgroundColor":"00000000",
            "multiLine":"true","singleLineScroll":"false","lineSpacing":"1","glowColor":"030710ff","glowSize":"1","zIndex":"45"},extra=False)
    menu.find(".//iconNewGame").text=LOOK+"slot-new.png"


def grid(v):
    element(v,"imagegrid","gamegrid",{"pos":"${u36.card16}","size":"${u36.card17}","autoLayout":"${u36.card18}",
              "peekSize":"${u36.card19}","padding":"8 8 8 8","margin":"7 7","imageSource":"image",
              "gameImage":ART+"empty.png","folderImage":ART+"games.png","autoLayoutSelectedZoom":"1",
              "showVideoAtDelay":"${videoDelay}","scrollbarSize":"0.00469","scrollbarCorner":"0.45",
              "scrollbarColor":"${accent}","scrollbarTrackColor":"${rail}","scrollLoop":"true","animateSelection":"false"},extra=False)
    tile=card_surface(v,"${u36.card15}")
    applications="({system:theme} == 'tools' || {system:theme} == 'emulators')"
    caption_shade(tile,show="!"+applications)
    element(tile,"text","gameTitle",{"pos":"${cardTitlePos}","size":"${cardTitleSize}","text":"{game:cleanName}",
            "fontPath":DISPLAY_FONT,"fontSize":font_size(15),"verticalAlignment":"bottom","color":"ffffff",
            "multiLine":"${cardTitleWrap}","maxLines":"${cardTitleLines}","lineSpacing":"1.0","visible":"!"+applications,"glowColor":"030710ff","glowSize":"1","zIndex":37})
    badges(tile,True)
    # Only actual playback emits these events. The supplemental text is still available in the sidebar.
    for overlay in tile:
        if overlay.tag not in ("image","text"):
            continue
        opacity="0.12" if overlay.get("name") in ("captionShade","badgeShade") else "0.24"
        for event,target,duration in (("videoplaying",opacity,"100"),("videostopped","1","0")):
            story=ET.SubElement(overlay,"storyboard",event=event)
            ET.SubElement(story,"animation",property="opacity",to=target,duration=duration)
    element(tile,"image","appSurface",{"pos":"0 0","size":"1 1","path":LOOK+"extra-tools.png",
            "roundCorners":"${tileRadius}","visible":applications,"zIndex":24})
    element(tile,"image","appSymbol",{"pos":".5 .37","origin":".5 .5","maxSize":".52 .53",
            "path":utility_icon("game"),"default":LOOK+"symbol-tool.png","linearSmooth":"true","visible":applications,"zIndex":30})
    element(tile,"text","appTitle",{"pos":".06 .65","size":".88 .31","text":"{game:cleanName}",
            "fontPath":DISPLAY_FONT,"fontSize":font_size(16),"color":"${ink}",
            "alignment":"center","verticalAlignment":"center","multiLine":"true","maxLines":"2",
            "lineSpacing":"1.0","visible":applications,"zIndex":38})
    ring(tile,duration=0)
    element(v,"image","gridtile.image",{"roundCorners":"${tileRadius}"},extra=False)
    element(v,"video","gridtile.video",{"effect":"none","fadeTime":"0.25","exclusiveSnapshot":"true","roundCorners":"${tileRadius}"},extra=False)
    # The same tint as the console's preview in the console view, on these systems' own lists
    for theme,tint in SCREEN_TINT.items():
        tinted=element(v,"video","gridtile.video",{"color":tint,"saturation":"0"},extra=False)
        tinted.set("if","{system.theme} == '"+theme+"'")
    element(v,"gridtile","selected",{"padding":"0 0","imageColor":"ffffffff",
            "backgroundEdgeColor":"ffffffff","backgroundCenterColor":"ffffffff"},extra=False)
    element(v,"text","gridtile.label",{"visible":"false"},extra=False)
    element(v,"text","gridtile.label.selected",{"visible":"false"},extra=False)


def tile_badge_geometry(root):
    # Use the actual native grid geometry so marks keep a constant pixel size across aspect ratios.
    # The layout generator already has the corresponding card dimensions for every input condition.
    for block in list(root.findall("variables")):
        sizes=block.findtext("u36.card17")
        if not sizes:continue
        cols,rows=map(int,block.findtext("u36.card18").split())
        width,height=map(float,sizes.split())
        w=(640*width-16-(cols-1)*7)/cols
        h=(480*height-16-(rows-1)*7)/rows
        compact=block.get("ifSubset")==f"{setting.DENSITY}:compacta"
        mark,margin,gap=(13,5,2) if compact else (17,7,4)
        save_x=w-margin-2*mark-gap
        pitch=min(11 if compact else 14,int((save_x-margin-3)/5))
        metrics={"cardStarsPos":(margin,margin+(mark-pitch)/2),"cardStarsSize":(5*pitch,pitch),
                 "cardHeartPos":(w-margin-mark,margin),"savedPos":(save_x,margin),
                 "badgeMark":(mark,mark),"badgeShadeSize":(w,margin+mark+(9 if compact else 12))}
        # Keep both lines above the lower edge on portrait cards in either density.
        portrait=h>w
        caption=34 if portrait else .195*h
        prop(block,"cardTitlePos",norm(.045*w,.955*h-caption,w,h))
        prop(block,"cardTitleSize",norm(.91*w,caption,w,h))
        prop(block,"cardTitleWrap",str(portrait).lower())
        prop(block,"cardTitleLines",2 if portrait else 1)
        for tag,(x,y) in metrics.items():
            prop(block,tag,norm(x,y,w,h))


def details_column(v, consoles, action, action_key="cta-x.png"):
    """A game's sheet in the left column: the console, the art, the title, the plays, the time and the players,
    the credits, the last play, the action, the rating, the genre and the description. The game list and the
    game switcher draw the same one; consoles=(L1, R1 conditions) puts the keys that change console beside it."""
    if consoles:
        key(v,"L1",6,37,consoles[0])
        key(v,"R1",163,37,consoles[1])
    identity(v,0,context=True,show=GAMES)
    # The native handler owns X throughout the game list; unsupported emulators explain their save model.
    selected_game="("+GAMES+") && !empty({game:cleanName}) && !{game:folder}"
    cta(v,"save",0,368,selected_game,action,key_art=action_key)
    badges(v)
    genre_visible="("+GAMES+") && !empty({game:genre}) && {game:genre} != 'Desconocido' && {game:genre} != 'Unknown'"
    image(v,"genreIcon",15,GENRE_Y+2,12,12,ART+"genre.png",show=genre_visible)
    text(v,"genre",32,GENRE_Y-3,155,23,"{game:genre}",11.5,show=genre_visible,scroll=True)
    image(v,"art",14,84,172,127,'firstfile({game:${detailPrimary}}, {game:${detailFallback}}, "'+ART+'empty.png")',contain=True,show=GAMES,z=25)
    game_title(v,"game",15,211,172,"{game:name}",GAMES,align="bottom")
    image(v,"sessionBand",5,274,190,40,LOOK+"metric-band.png",show=GAMES,z=24)
    for x,width,inset,name,icon,value,label in [
            (5,52,8,"Plays","played",'{game:playcount} > 0 ? tostring({game:playcount}) : "—"',
             '{game:playcount} == 1 ? "vez" : "veces"'),
            (57,87,2,"Time","time",'tostring({game:gametime}) + "s"',"tiempo"),
            (139,56,8,"Players","players",'empty({game:players}) ? "—" : {game:players}','{game:players} == "1" ? "jugador" : "jugadores"')]:
        node=counter_cell(v,name,x,279,width,icon,value,label,GAMES,inset=inset)
        if name=="Time":
            duration_counter(v,node,x,279,width,GAMES)
    game_credits(v,"game",15,325,172,"{game:developer}","year({game:releasedate})",GAMES)
    text(v,"lastLabel",15,342,70,16,"Última vez",11,color="${muted}",show=GAMES)
    has_date="!empty(year({game:lastplayed}))"
    text(v,"lastValue",86,341,101,18,'day({game:lastplayed}) + "/" + month({game:lastplayed}) + "/" + year({game:lastplayed})',
         12,weight="Bold",align="right",show="("+GAMES+") && "+has_date)
    text(v,"lastMissing",86,341,101,18,"—",12,weight="Bold",align="right",show="("+GAMES+") && !("+has_date+")")
    text(v,"description",15,407,172,67,"{game:desc}",11.5,weight="Regular",color="${muted}",wrap=True,scroll=True,show="("+GAMES+") && !empty({game:desc}) && {game:desc} != 'Desconocido' && {game:desc} != 'Unknown'")


def games(root):
    v=view(root,"grid")
    element(v,"text","logoText",{"visible":"false"},extra=False)
    element(v,"image","background",{"path":LOOK+"canvas.png","pos":"0 0","size":"1 1","zIndex":"0"},extra=False)
    image(v,"detailsPanel",0,31,200,449,LOOK+"panel.png",z=1,show=GAMES)
    header(v)
    grid(v)
    key(v,"L2",208,37)
    text(v,"prevPage",240,36,65,24,"Anterior",11.5,weight="Bold")
    metrics(v,311,33,show=GAMES,compact=True)
    text(v,"nextPage",523,36,78,24,"Siguiente",11.5,align="right",weight="Bold")
    key(v,"R2",602,37)
    details_column(v,("("+GAMES+") && !empty({system:prevConsole})","("+GAMES+") && !empty({system:nextConsole})"),
                   [("","Abrir partidas","{game:saveStatesSupported}"),("InGame","Partidas","!{game:saveStatesSupported}")])
    # A utility library has the full canvas and its native primary action.
    u=view(root,"grid",UTILITY)
    for n in ("buttonL2","prevPage"):
        original=next(e for e in v if e.get("name")==n)
        el=element(u,original.tag,n,extra=True)
        prop(el,"pos",norm(11 if n=="buttonL2" else 40,39 if n=="buttonL2" else 36))
    text(u,"utilityContext",100,37,440,23,
         '{system:theme} == "tools" ? "Herramientas" : ({system:theme} == "emulators" ? "Emuladores" : "Capturas")',
         14,align="center",weight="Black")
    element(u,"imagegrid","gamegrid",{"pos":norm(0,64),"size":"1 .84","autoLayout":"3 2","peekSize":".025"},extra=False)
    apps=view(root,"grid","{system.name} == 'tools' || {system.name} == 'emulators'")
    element(apps,"imagegrid","gamegrid",{"pos":norm(0,64),"size":norm(640,416),"autoLayout":"3 3",
            "peekSize":"0","padding":"8 8 8 8","margin":"8 8","showVideoAtDelay":"-1"},extra=False)
    element(apps,"image","gridtile.image",{"visible":"false"},extra=False)
    compact=view(root,"grid",UTILITY)
    compact.set("ifSubset",f"{setting.DENSITY}:compacta")
    element(compact,"imagegrid","gamegrid",{"autoLayout":"4 3"},extra=False)
