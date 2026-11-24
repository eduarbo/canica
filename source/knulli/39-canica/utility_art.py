"""Scalable pictograms for collections and utilities, on transparent canvases."""

import shutil

# Named defaults cover common tools on a fresh installation. Private app names can use local overrides.
STOCK_TOOLS = {
    "VaixTerm":"terminal", "Terminal":"terminal", "Continuar último juego":"resume", "Resume":"resume",
    "Estado de la consola":"health", "System status":"health", "Reparar Wi-Fi":"network", "Wi-Fi":"network",
    "Respaldo ahora":"backup", "Backup":"backup", "Sincronizar ahora":"sync", "Sync":"sync",
    "Bluetooth":"audio", "Sincronizar biblioteca":"library-sync", "PPSSPP":"handheld", "ScummVM":"pointer",
}

SYMBOLS = {
    "library": '<path class="solid" d="M8 20 30 9l25 9-22 12z"/><path d="m8 29 25 11 22-12M8 39l25 12 22-12"/><path class="light" d="m18 19 14-6 12 4"/>',
    "chef": '<path class="solid" d="M19 37c-8 0-13-6-12-13s8-12 15-10c3-6 9-9 15-7 4 1 7 4 9 8 7-2 14 3 14 10 0 7-5 12-13 12l-2 12H21z"/><path class="light" d="m24 33 2 10m8-12v12m9-10-2 10M21 53h24"/>',
    "recent": '<path d="M9 28A23 23 0 1 1 14 47"/><path class="light" d="m7 14 1 15 14-3M32 18v15l10 6"/><circle class="filled" cx="32" cy="33" r="3"/>',
    "tool": '<path class="solid" d="M37 13a13 13 0 0 1 15-5l-9 10 4 7 10-6a13 13 0 0 1-16 14L20 54a6 6 0 0 1-9-9l23-20a14 14 0 0 1 3-12Z"/><circle class="light" cx="16" cy="49" r="1.6"/>',
    "chip": '<rect class="solid" x="15" y="15" width="34" height="34" rx="7"/><rect class="light" x="23" y="23" width="18" height="18" rx="3"/><path d="M22 8v6m10-6v6m10-6v6M22 50v6m10-6v6m10-6v6M8 22h6m-6 10h6m-6 10h6m36-20h6m-6 10h6m-6 10h6"/>',
    "gallery": '<path d="m12 22-4 28a3 3 0 0 0 3 4l35 4"/><rect class="solid" x="17" y="10" width="39" height="36" rx="5"/><circle class="filled" cx="44" cy="20" r="3.8"/><path class="light" d="m19 37 10-11 9 9 5-5 11 10"/>',
    "audio": '<path class="solid" d="M12 13c-4 0-7 4-7 9s3 9 8 9h3v17a4 4 0 0 0 8 0V24c0-6-5-11-12-11Z"/><path class="solid" d="M52 13c4 0 7 4 7 9s-3 9-8 9h-3v17a4 4 0 1 1-8 0V24c0-6 5-11 12-11Z"/><path class="light" d="M10 20c1-3 4-3 7-1m30 0c3-2 6-2 7 1M19 44v4m26-4v4"/>',
    "resume": '<path d="M12 21a23 23 0 1 1-2 23M8 11l3 13 13-3"/><path class="filled" d="m28 22 15 10-15 10z"/>',
    "health": '<rect class="solid" x="10" y="9" width="44" height="46" rx="9"/><path class="light" d="M16 29h8l4-9 7 17 5-9h9"/><path d="M18 46h7m-3.5-3.5v7"/><circle class="filled" cx="43" cy="45" r="2"/>',
    "network": '<path d="M5 22a42 42 0 0 1 54 0M12 30a31 31 0 0 1 40 0"/><path class="light" d="M20 38a20 20 0 0 1 24 0m-16 8a7 7 0 0 1 8 0"/><circle class="filled" cx="32" cy="51" r="3"/>',
    "backup": '<path class="solid" d="M10 33 16 19h11m13 0h8l6 14v14a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4Z"/><path class="light" d="M11 35h12l4 6h10l4-6h12M32 29V7m-8 8 8-8 8 8"/>',
    "sync": '<path d="M9 29a23 23 0 0 1 39-14l5 6m1-13-1 14-14-1"/><path class="light" d="M55 35a23 23 0 0 1-39 14l-5-6m-1 13 1-14 14 1"/>',
    "library-sync": '<path class="solid" d="M9 11h8v36H9zm13 0h8v36h-8z"/><path class="light" d="M7 53h26m4-31a11 11 0 0 1 17 2l3 5m0-9v10l-9-1m7 12a11 11 0 0 1-17 0l-2-4m0 8v-9l9 1"/>',
    "saves": '<path d="M12 20v29a5 5 0 0 0 5 5h26"/><path class="solid" d="M22 9h22l9 9v24a4 4 0 0 1-4 4H25a4 4 0 0 1-4-4V13Z"/><path class="light" d="M29 11v10h14V11M29 43V30h16v13"/>',
    "terminal": '<rect class="solid" x="6" y="10" width="52" height="43" rx="7"/><path d="M8 20h48"/><path class="light" d="m16 28 6 6-6 6m13 0h12"/>',
    "folder": '<path class="solid" d="M7 19a4 4 0 0 1 4-4h13l5 6h23a4 4 0 0 1 4 4v21a5 5 0 0 1-5 5H12a5 5 0 0 1-5-5z"/><path class="light" d="M10 29h42"/>',
    "handheld": '<rect class="solid" x="5" y="16" width="54" height="33" rx="9"/><rect class="light" x="19" y="22" width="25" height="19" rx="2"/><path d="M9 32h7m-3.5-3.5v7"/><circle class="filled" cx="50" cy="29" r="1.8"/><circle class="filled" cx="54" cy="35" r="1.8"/>',
    "pointer": '<rect class="solid" x="7" y="11" width="49" height="36" rx="5"/><path d="M16 54h22m-10-7v6"/><path class="light" d="m27 21 4 22 6-7 8-2z"/>',
}
EXTRAS = (
    ("auto-allgames","library","Todos los juegos"),("auto-favorites","chef","Sugerencias del chef"),
    ("auto-lastplayed","recent","Últimos jugados"),("tools","tool","Herramientas"),
    ("emulators","chip","Emuladores"),("imageviewer","gallery","Capturas"),
)


def generate_icons(directory, palette, draw):
    amber=palette["motif"]=="ticket"
    accents=(("ffd29a","f3a98c","a3ddca","ffd078","a3cde5","e4aacc") if amber else
             ("b4b6ff","f9abc9","95e1d0","ffce96","97d8f6","c9b2ff"))
    colors=dict(zip((symbol for _,symbol,_ in EXTRAS),accents))
    colors.update(dict(zip(("audio","resume","health","network","backup","sync","library-sync","saves",
                            "folder","handheld","pointer","terminal"),
                           (accents[i] for i in (4,2,0,4,3,2,0,5,3,4,2,4)))))
    for symbol,paths in SYMBOLS.items():
        accent=colors[symbol]
        style=(f'<style>.solid{{fill:#{accent};fill-opacity:.17}}.light{{stroke:#{palette["ink"]}}}'
               f'.filled{{fill:#{accent};stroke:none}}</style>')
        group=f'<g fill="none" stroke="#{accent}" stroke-width="3.1" stroke-linecap="round" stroke-linejoin="round">{paths}</g>'
        draw(directory,"symbol-"+symbol,128,128,style+'<g transform="scale(2)">'+group+'</g>')
    names=directory/"tools"
    names.mkdir()
    for title,symbol in STOCK_TOOLS.items():
        shutil.copyfile(directory/("symbol-"+symbol+".png"),names/(title+".png"))
    for theme,symbol,_ in EXTRAS:
        accent=colors[symbol]
        surface=(f'<defs><radialGradient id="halo" cx=".45" cy=".32" r=".75"><stop stop-color="#{accent}" '
                 f'stop-opacity=".21"/><stop offset="1" stop-color="#{accent}" stop-opacity="0"/></radialGradient></defs>'
                 f'<rect width="192" height="184" rx="10" fill="#{palette["panel"]}"/>'
                 '<rect width="192" height="184" rx="10" fill="url(#halo)"/>')
        draw(directory,"extra-"+theme,192,184,surface)
