"""Native PNG artwork. SVG paths are original geometric drawings in a 24-pixel grid."""
import subprocess
from utility_art import generate_icons

PATHS = {
    "games": "M5 3h13l2 2v16H4V4z M7 4v6h10V4 M8 16h8m-8 3h6",
    "favs": "M12 20 4 12C-1 5 7 0 12 7c5-7 13-2 8 5z",
    "played": "M4 9a8 8 0 1 1 0 7 M2 4v6h6 M12 7v6l4 2",
    "timer": "M9 2h6m-3 0v3m6 2 2-2 M20 13a8 8 0 1 1-16 0 8 8 0 1 1 16 0z M12 8v6l3 2",
    "star": "m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z",
    "handheld": "M5 3h14v16l-3 3H5z M8 6h8v7H8z M7 17h4m-2-2v4m5-2h2",
    "pad": "M6 7h12l2 2 2 8-2 2-5-4H9l-5 4-2-2 2-8z M5 11h5m-2-2v4m7-2h1m2 2h1",
    "arcade": "M6 2h12l1 4-2 1-1 7 4 3v5H4v-5l3-3-2-7z M8 7h7l-1 5H9z M7 17h10",
    "monitor": "M2 4h20v13H2z M9 21h6m-3-4v4",
    "tools": "m4 18 9-9a6 6 0 0 1 7-7l-4 4 2 2 4-3a6 6 0 0 1-8 7l-8 9z",
    "image": "M2 4h20v16H2z M3 17l6-6 4 4 3-3 5 6 M15 8h1",
    "grid": "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    "disk": "M4 3h13l4 4v14H3V3z M7 4v6h9V4 M7 20v-6h10v6",
    "slots": "M3 5h18v4H3z M3 12h18v6H3z M6 15h3",
    "genre": "M2 4h10l10 10-8 8L2 10z M6 7h1",
}


def draw(out, name, width, height, content):
    source = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{content}</svg>'
    subprocess.run(["rsvg-convert", "-o", str(out / (name + ".png"))],
                   input=source.encode(), check=True)


def glyph(name, color, x=0, y=0, size=24, fill="none"):
    return (f'<g transform="translate({x} {y}) scale({size / 24})">'
            f'<path d="{PATHS[name]}" stroke="#{color}" stroke-width="1.8" '
            f'fill="{fill}" stroke-linejoin="round" stroke-linecap="round"/></g>')


def rect(x, y, w, h, r, fill, stroke="none"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>'


def gradient(stops):
    colors = "".join(f'<stop offset="{i / (len(stops)-1):.3f}" stop-color="#{c}"/>' for i,c in enumerate(stops))
    return f'<defs><linearGradient id="g" x2="1" y2="1" gradientUnits="objectBoundingBox">{colors}</linearGradient></defs>'


def marble(out, palette):
    vein = gradient(palette["stops"])
    clip = '<clipPath id="ball"><circle cx="24" cy="24" r="21"/></clipPath>'
    body = f'<circle cx="24" cy="24" r="21" fill="#{palette["panel"]}"/>'
    ribbon = '<path d="M-1 33C13 41 22 25 29 16C35 9 41 7 50 9C38 11 34 20 29 28C21 42 9 46 -1 39Z" fill="url(#g)"/>'
    glint = '<path d="M10 18Q12 10 21 8" fill="none" stroke="#fff" stroke-opacity=".85" stroke-width="2.7" stroke-linecap="round"/>'
    rim = f'<circle cx="24" cy="24" r="21" fill="none" stroke="#{palette["accent"]}" stroke-width="2"/>'
    draw(out, "canica", 48, 48, vein + clip + body + '<g clip-path="url(#ball)">' + ribbon + glint + '</g>' + rim)


def navigation_art(out,palette):
    accent="#"+palette["accent"]
    ink="#"+palette["ctaInk"]
    bell='<path d="M4 12c1.5-1.4 1.7-2.8 1.7-5a4.3 4.3 0 0 1 8.6 0c0 2.2.2 3.6 1.7 5l.8 1.2H3.2Z" fill="'+ink+'"/><path d="M8 15q2 3 4 0" fill="'+ink+'"/>'
    draw(out,"notice",20,18,bell)
    draw(out,"resume-play",13,13,f'<path d="M2.25 1.8q0-1 1-.45l8.3 4.65q.8.5 0 1L3.25 11.65q-1 .55-1-.45Z" fill="{accent}"/>')
    for name,path in (("games","games"),("favs","favs"),("played","played")):
        draw(out,"metric-"+name,20,20,glyph(path,palette["accent"],0,0,20))
    outline=f'fill="none" stroke="{accent}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"'
    draw(out,"metric-time",20,20,f'<g {outline}><circle cx="10" cy="10" r="7.6"/><path d="M10 5v5l3.4 1.8"/></g>')
    draw(out,"metric-players",20,20,f'<g {outline}><circle cx="7.2" cy="6.4" r="2.9"/><path d="M1.7 16v-1.2c0-4.7 11-4.7 11 0V16z M13 3.9c4.4 1 4.4 5.1.4 6.4 M14.4 11.8q4 .5 4 4.4"/></g>')
    draw(out,"metric-band",190,40,rect(0,0,190,40,5,"#"+palette["metricBand"]))
    left,right=palette["ctaStops"]
    fill=f'<defs><linearGradient id="cta"><stop stop-color="#{left}"/><stop offset="1" stop-color="#{right}"/></linearGradient></defs>'
    draw(out,"cta",174,31,fill+rect(0,0,174,31,15.5,"url(#cta)"))
    draw(out,"cta-x",16,16,f'<circle cx="8" cy="8" r="7.8" fill="#{palette["ctaInk"]}"/><path d="m5.8 5 4.4 6m0-6-4.4 6" fill="none" stroke="#{left}" stroke-width="1.9" stroke-linecap="round"/>')


def category_art(out):
    dark = "#252741"
    def path(d, fill):
        return f'<path d="{d}" fill="{fill}" stroke-linejoin="round"/>'
    def dot(x,y,r,color):
        return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
    dpad = path("M0 3h3V0h3v3h3v3H6v3H3V6H0z",dark)
    bodies = {
        "extras": rect(9,2,19,23,3,"#6f95ca")+rect(4,7,20,23,3,"#c3e5ed")
                  +rect(7,10,14,10,1,dark)+path("m9 18 3-4 2 2 2-3 3 5z","#84cbb9")
                  +rect(8,23,12,2,1,"#4a6d83"),
        "eight-bit": rect(1,7,30,19,3,"#eee2cd")+rect(3,10,26,12,1,"#444352")
                  +'<g transform="translate(5 12)">'+dpad.replace(dark,"#e0e6e5")+'</g>'
                  +dot(21,18,2.5,"#ff776e")+dot(26,16,2.5,"#ff776e")
                  +rect(14,16,4,1.5,.5,"#d6bfaa"),
        "sixteen-bit": path("M9 7h14a8.5 8.5 0 0 1 0 17c-4 0-5-3-8-3s-4 3-7 3A8.5 8.5 0 0 1 9 7z","#ddd4ed")
                  +'<g transform="translate(4 11)">'+dpad+'</g>'
                  +dot(21,13,2,"#7057bd")+dot(25,16,2,"#7057bd")+dot(21,19,2,"#9e86cc")+dot(17,16,2,"#9e86cc"),
        "thirty-two-bit": path("M9 6h14c3 0 5 2 6 6l2 12c0 3-3 4-5 2l-5-6H11l-5 6c-2 2-5 1-5-2l2-12c1-4 3-6 6-6z","#bad6dd")
                  +'<g transform="translate(5 9) scale(.8)">'+dpad+'</g>'+dot(12,18,3,dark)+dot(20,18,3,dark)
                  +dot(23,10,1.6,"#326d6b")+dot(26,13,1.6,"#a95862"),
        "handheld": path("M7 1h17a1 1 0 0 1 1 1v23l-5 6H7a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2z","#d8c9ed")
                  +rect(8,4,14,12,2,dark)+rect(10,6,10,7,1,"#b9d889")
                  +'<g transform="translate(7 18) scale(.8)">'+dpad+'</g>'+dot(20,21,2,"#a94777")+dot(23,18,1.8,"#a94777"),
        "arcade": path("M8 1h18v5l-3 2-1 8 5 3v11H5V19l4-4-2-8-2-2z","#f8be7c")
                  +rect(9,3,15,3,1,"#9d4655")+path("m10 8 11 0-1.5 7h-8z",dark)
                  +path("m12 9 7 0-4.5 4h-2z","#8fd3d2")+rect(7,19,17,3,1,dark)
                  +rect(10,24,10,4,1,"#a16b58"),
        "computer": rect(2,3,28,21,3,"#a5d6dd")+rect(5,6,21,14,2,dark)
                  +path("m8 10 3 3-3 3 1 1 5-4-5-4z","#91deb3")+rect(15,15,6,1.8,0,"#91deb3")
                  +path("M6 25h20l4 4H2z","#d6e1df")+rect(9,26,14,1,0,"#5f8a99")
    }
    for slug,body in bodies.items():
        for size in (20,24,34):
            draw(out,f"category-{slug}-{size}",size,size,f'<g transform="scale({size/32})">{body}</g>')



def generate(out, palettes):
    out.mkdir(parents=True)
    for name in PATHS:
        draw(out, name, 24, 24, glyph(name, "dbe6f5"))
    heart="M10 17.6 3.3 11C-1.1 6.3 4.9.2 9.1 4.5l.9 1 .9-1C15.1.2 21.1 6.3 16.7 11Z"
    for state,color in [("on","ff6383"),("off","99a8bb")]:
        fill="#"+color if state=="on" else "none"
        outline=f'<path d="{heart}" fill="none" stroke="#080d17" stroke-width="3.5" stroke-linejoin="round"/>'
        mark=f'<path d="{heart}" fill="{fill}" stroke="#{color}" stroke-width="{1.1 if state=="on" else 1.7}" stroke-linejoin="round"/>'
        draw(out,"heart-"+state,20,20,mark)
        draw(out,"detail-heart-"+state,20,20,outline+mark)

    star="M8 1.4l2.0 4.2 4.6.6-3.3 3.3.8 4.6L8 12l-4.1 2.1.8-4.6-3.3-3.3 4.6-.6Z"
    for count in range(6):
        stars=[]
        for index in range(5):
            fill,edge=("#ffda70","#ffe6a6") if index<count else ("#263143","#8490a2")
            stars.append(f'<g transform="translate({16*index} 0)" stroke-linejoin="round">'
                         f'<path d="{star}" stroke="#111824" stroke-width="2.4"/>'
                         f'<path d="{star}" fill="{fill}" stroke="{edge}" stroke-width="1"/></g>')
        draw(out,f"stars-{count}",80,16,"".join(stars))
    fade=('<defs><linearGradient id="down" x2="0" y2="1"><stop stop-color="#070d18" stop-opacity=".79"/>'
          '<stop offset=".32" stop-color="#070d18" stop-opacity=".68"/><stop offset="1" stop-color="#070d18" stop-opacity="0"/></linearGradient></defs>')
    draw(out,"badge-fade",128,36,fade+'<path d="M0 8Q0 0 8 0H120Q128 0 128 8V36H0Z" fill="url(#down)"/>')
    draw(out,"dev",12,12,'<g stroke="#b5bece" stroke-width="1" fill="none"><rect x="1.5" y="3" width="9" height="7" rx="1"/><path d="M4 3V1.5h4V3M2 5.5h8"/></g>')
    draw(out,"empty",160,100,rect(0,0,160,100,6,"#131d2b")+glyph("games","68778b",67,36,26))
    draw(out,"shade",20,72,'<defs><linearGradient id="s" x2="0" y2="1"><stop stop-color="#050811" stop-opacity="0"/><stop offset="1" stop-color="#050811" stop-opacity=".97"/></linearGradient></defs>'+rect(0,0,20,72,0,"url(#s)"))
    disk='<path fill="#d9ecf3" fill-rule="evenodd" d="M2 2h11l3 3v11H2z M5 3v4h6V3z M5 10v5h8v-5z"/><path d="M7 12h4" stroke="#d9ecf3" stroke-width="1.3"/>'
    edge='<path d="M2 2h11l3 3v11H2Z" fill="none" stroke="#101927" stroke-width="1.8" stroke-linejoin="round"/>'
    draw(out,"save-mark",17,17,edge+disk)
    category_art(out)
    for key,p in palettes.items():
        d=out/key
        d.mkdir()
        generate_icons(d,p,draw)
        base=rect(0,0,192,144,8,"#"+p["panel"])
        draw(d,"slot-empty",192,144,base+glyph("disk",p["muted"],79,38,34))
        draw(d,"slot-new",192,144,base+f'<path d="M96 39v32m-16-16h32" stroke="#{p["accent"]}" stroke-width="4" stroke-linecap="round"/>')
        # Nine-patches keep rounded keycaps and a one-pixel lower edge at every key width.
        for name,fill,edge in (
            ("search-key", "2b3a52" if key=="iris" else "413028", p["rail"]),
            ("search-action", "19283c" if key=="iris" else "2d241e", p["rail"]),
            ("search-focus", p["accent"], p["stops"][0]),
            ("search-active", "686789" if key=="iris" else "856944", p["accent"]),
        ):
            cap=rect(0,1,24,23,5,"#"+edge)+rect(0,0,24,22,5,"#"+fill)
            draw(d,name,24,24,cap)

        marble(d,p)
        navigation_art(d,p)
        focus=rect(0,0,182,33,6,"#283651" if key=="iris" else "#35281f")
        focus+=rect(0,5,3,23,1,"#"+p["accent"])
        draw(d,"category-selected",182,33,focus)
        grad=gradient(p["stops"])
        draw(d,"canvas",4,4,rect(0,0,4,4,0,"#"+p["canvas"]))
        draw(d,"panel",64,96,gradient([p["panel"],p["canvas"],p["panel"]])+rect(0,0,64,96,0,"url(#g)"))
        for name,color in [("top",p["top"]),("solid",p["panel"]),("clear","ffffff")]:
            draw(d,name,4,4,rect(0,0,4,4,0,"#"+color))
        amber=p["motif"]=="ticket"
        if amber:
            border='<rect x=".5" y=".5" width="47" height="47" rx="4" fill="none" stroke="#e9b768" opacity=".42"/>'
            for path,color in (("M1.5 22V1.5H22","ffd68f"),("M26 1.5H46.5V22","ffae63"),
                               ("M1.5 26V46.5H22","ffae63"),("M26 46.5H46.5V26","ffde9a")):
                border+=f'<path d="{path}" fill="none" stroke="#{color}" stroke-width="3"/>'
            draw(d,"focus",48,48,border)
        else:
            draw(d,"focus",32,32,grad+'<rect x="1.5" y="1.5" width="29" height="29" rx="6.5" fill="none" stroke="url(#g)" stroke-width="3"/>')
        wash=('<defs><linearGradient id="w" x2="0" y2="1"><stop stop-color="#100b0b" stop-opacity=".40"/>'
              '<stop offset=".38" stop-color="#130c09" stop-opacity="0"/><stop offset="1" stop-color="#130c09" stop-opacity=".94"/></linearGradient></defs>'
              +rect(0,0,136,131,4,"url(#w)")+
              ''.join(f'<path d="M0 {y}h136" stroke="#07070b" opacity=".07"/>' for y in range(0,131,4)))
        draw(d,"card-wash",136,131,wash)
        # Over a console card's game screen, under its logo and console: both read on any capture
        dim=.35 if amber else .5
        draw(d,"card-dim",136,131,f'<rect width="136" height="131" fill="#{p["canvas"]}" fill-opacity="{dim}"/>')
        draw(d,"year",32,15,rect(0,0,32,15,2,"#17130f"))
        for name in ["handheld","pad","arcade","monitor","tools","image","grid","favs","played","games"]:
            # Console covers are drawn here. Library snapshots can replace the backdrop at runtime.
            art=gradient([p["panel"],p["canvas"]])+rect(0,0,136,133,9,"url(#g)")
            art+=''.join(f'<path d="M0 {y}l136 -26" stroke="#{p["accent"]}" opacity=".045"/>' for y in range(0,168,8))
            draw(d,"card-"+name,136,133,art+glyph(name,p["accent"],39,22,58))
