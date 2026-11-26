"""Canica's words in its two languages.

English is the default; Spanish applies on a console whose language is Spanish (system.language es or es_*),
through ES's lang attribute, so a Spanish console reads exactly what it read before English existed. Element
texts and option names refer to ${tx.<key>} variables; layout that depends on a word's width gets its own
per-language variables (geo). Values must not contain =, <, > or ${: ES evaluates a variable holding any of
them as an expression.
"""
from xml.etree import ElementTree as ET

SPANISH = "es"   # ES matches it against the language part of system.language (es_MX -> es)

# key: (Spanish, English)
TEXT = {
    # Theme options (START > UI settings > theme configuration)
    "optStyle": ("Variante", "Variant"),
    "optDensity": ("Tarjetas de juegos", "Game cards"),
    "densityLarge": ("Grandes", "Large"),
    "densityCompact": ("Compactas", "Compact"),
    "optVideo": ("Vídeo en la tarjeta seleccionada", "Video on the selected card"),
    "videoOn": ("Reproducir", "Play"),
    "videoOff": ("Solo imagen", "Image only"),
    "optArt": ("Imagen de la ficha", "Details image"),
    "artBox": ("Carátula primero", "Box art first"),
    "artShot": ("Captura primero", "Screenshot first"),
    "optMotion": ("Vistas previas de consolas", "Console previews"),
    "motionOn": ("Animadas", "Animated"),
    "motionOff": ("Solo imágenes fijas", "Still images only"),
    "look.iris": ("Iris", "Iris"),
    "look.ambar": ("Ámbar", "Amber"),
    # Header
    "search": ("Buscar", "Search"),
    # Console view
    "library": ("Biblioteca", "Library"),
    "tab0": ("EXTRAS", "EXTRAS"),
    "tab1": ("8 BITS", "8 BITS"),
    "tab2": ("16 BITS", "16 BITS"),
    "tab3": ("32+ BITS", "32+ BITS"),
    "tab4": ("PORTÁTILES", "HANDHELDS"),
    "tab5": ("ARCADE", "ARCADE"),
    "tab6": ("PC Y MÁS", "PC & MORE"),
    "tabSubtitle0": ("Colecciones y utilidades", "Collections and utilities"),
    "games": ("juegos", "games"),
    "of": ("de", "of"),
    "favs": ("favs", "favs"),
    "played": ("jugados", "played"),
    "previewLatest": ("ÚLTIMO JUGADO", "LAST PLAYED"),
    "previewHistory": ("DEL HISTORIAL", "FROM YOUR HISTORY"),
    "previewSuggestion": ("SUGERENCIA", "SUGGESTION"),
    "today": ("Hoy", "Today"),
    "yesterday": ("Ayer", "Yesterday"),
    "continue": ("Continuar", "Continue"),
    "play": ("Jugar", "Play"),
    "nothingPlayed": ("Todavía no juegas nada aquí", "Nothing played here yet"),
    "toolOne": ("1 herramienta", "1 tool"),
    "toolMany": ("herramientas", "tools"),
    "emulatorOne": ("1 emulador", "1 emulator"),
    "emulatorMany": ("emuladores", "emulators"),
    "shotOne": ("1 captura", "1 screenshot"),
    "shotMany": ("capturas", "screenshots"),
    "available": ("Disponibles", "Available"),
    "latestShot": ("Última captura", "Latest screenshot"),
    "noShots": ("Aún no hay capturas", "No screenshots yet"),
    # Extras cards
    "extra.auto-allgames": ("Todos los juegos", "All games"),
    "extra.auto-favorites": ("Sugerencias del chef", "Chef's picks"),
    "extra.auto-lastplayed": ("Últimos jugados", "Recently played"),
    "extra.tools": ("Herramientas", "Tools"),
    "extra.emulators": ("Emuladores", "Emulators"),
    "extra.imageviewer": ("Capturas", "Screenshots"),
    "extra.auto-continue": ("Continuar", "Continue"),
    # Game list and the game switcher
    "previous": ("Anterior", "Previous"),
    "next": ("Siguiente", "Next"),
    "openSaves": ("Abrir partidas", "Open saves"),
    "saves": ("Partidas", "Saves"),
    "playOnce": ("vez", "play"),
    "playMany": ("veces", "plays"),
    "time": ("tiempo", "time"),
    "playerOne": ("jugador", "player"),
    "playerMany": ("jugadores", "players"),
    "lastTime": ("Última vez", "Last played"),
    "tools": ("Herramientas", "Tools"),
    "emulators": ("Emuladores", "Emulators"),
    "screenshots": ("Capturas", "Screenshots"),
    "switcherTitle": ("CONTINUAR", "CONTINUE"),
}

# Dates as the theme writes them: day/month/year in Spanish, month/day/year in English. {d} is the date binding.
DATE = ('day({d}) + "/" + month({d}) + "/" + year({d})', 'month({d}) + "/" + day({d}) + "/" + year({d})')

# Variables the frontend itself reads (search keyboard, saved games), in the same pairs
ENGINE = {
    "esSearchTitle": ("Buscar juegos", "Search games"),
    "esSearchHint": ("Título del juego", "Game title"),
    "esSearchClear": ("Limpiar", "Clear"),
    "esSearchSubmit": ("Buscar", "Search"),
    "esWordComplete": ("Completar palabra", "Complete word"),
    "esWordStart": ("Palabras frecuentes", "Common words"),
    "esWordNext": ("Siguiente palabra", "Next word"),
    "esWordEmpty": ("Sin sugerencias de palabra", "No word suggestions"),
    "esNoPickControls": ("L1  Borrar letra     ·     X  Limpiar     ·     B  Volver     ·     START  Buscar",
                         "L1  Delete letter     ·     X  Clear     ·     B  Back     ·     START  Search"),
    "esWordControls": ("← →  Elegir palabra     ·     A  Insertar     ·     B  Teclado     ·     START  Buscar",
                       "← →  Choose word     ·     A  Insert     ·     B  Keyboard     ·     START  Search"),
    "esSearchShortcuts": ("L2  Completar     ·     R2  Elegir     ·     L1  Borrar     ·     X  Limpiar     ·     B  Volver     ·     START  Buscar",
                          "L2  Complete     ·     R2  Choose     ·     L1  Delete     ·     X  Clear     ·     B  Back     ·     START  Search"),
    "esSaveToday": ("Hoy", "Today"),
    "esSaveYesterday": ("Ayer", "Yesterday"),
    "esSaveUnknownDate": ("Sin fecha", "No date"),
    "esNoSaveStatesText": ("Partidas\n\nEste emulador no ofrece estados rápidos en este menú. Si el juego guarda progreso, puedes cargarlo desde el propio juego.",
                           "Saves\n\nThis emulator offers no save states in this menu. If the game saves its progress, load it from the game itself."),
}

# The collection previews' headings (Extras)
HEADINGS = {
    "continue": ("CONTINUAR", "CONTINUE"),
    "recent": ("ÚLTIMOS JUGADOS", "RECENTLY PLAYED"),
    "all": ("DE TU BIBLIOTECA", "FROM YOUR LIBRARY"),
    "favorites": ("SUGERENCIAS DEL CHEF", "CHEF'S PICKS"),
}

# English names and descriptions of the catalogue's systems; Spanish ones come from the catalogue itself
LABELS = {
    "continue": "Continue", "all": "All games", "favorites": "Chef's picks", "recent": "Recently played",
    "arcadetate": "Vertical arcade", "tools": "Tools", "emulators": "Emulators", "imageviewer": "Screenshots",
}
DESCRIPTIONS = {
    "continue": "Your last fifteen games, each one where you left it.",
    "all": "Games from all your systems in a single list.",
    "favorites": "The games you marked as favorites on all your consoles.",
    "recent": "The games you opened, from the newest to the oldest.",
    "atari2600": "It brought swappable cartridges into millions of homes. About 30 million sold.",
    "nes": "The 1983 Famicom, which reached America as the NES. 61.91 million sold.",
    "mastersystem": "Sega's 8-bit console, successor to the Mark III; very popular in Brazil and Europe.",
    "pcengine": "By NEC and Hudson Soft: an 8-bit CPU with 16-bit graphics. In America, TurboGrafx-16.",
    "pcenginecd": "The first CD-ROM for a console: a PC Engine add-on, in Japan in 1988.",
    "megadrive": "Sega's 16-bit console, Genesis in America, with Sonic as its mascot from 1991.",
    "snes": "16-bit console with Mode 7 and a Sony sound chip. 49 million sold.",
    "neogeo": "The home version (AES) of SNK's MVS arcade: the same games, uncut.",
    "segacd": "CD-ROM drive for the Mega Drive, with more memory and sprite scaling and rotation.",
    "sega32x": "32-bit add-on for the Mega Drive, with two SH-2 processors like the Saturn's.",
    "psx": "The first console to pass 100 million: 102.49 million sold, on CD.",
    "n64": "It debuted Nintendo's analog stick with Super Mario 64. 32.93 million sold.",
    "dreamcast": "Sega's last console and the first with a built-in modem to play online.",
    "gb": "8-bit handheld with a four-shade green screen. With GB Color, 118.69 million.",
    "lynx": "The first handheld with a backlit color screen. Designed by Epyx, released by Atari.",
    "gamegear": "Sega's 8-bit handheld with a backlit color screen, based on the Master System.",
    "gbc": "The Game Boy's color successor: 56 colors at once and compatible with its games.",
    "wswan": "Bandai handheld designed by Gunpei Yokoi, creator of the Game Boy. Released only in Japan.",
    "ngpc": "SNK handheld with a microswitch stick, famous for its fighting games.",
    "wswanc": "WonderSwan in color, compatible with its games. It got remakes of Final Fantasy I, II and IV.",
    "gba": "32-bit handheld, the Game Boy's successor and backward compatible with it. 81.5 million sold.",
    "nds": "Dual-screen handheld, the lower one touch, with a microphone and Wi-Fi. 154.02 million.",
    "arcade": "Arcade games from many makers.",
    "arcadetate": "Vertical screen arcades (TATE), like 1942 or Galaga, in their original orientation.",
    "mame": "Arcade games that run on MAME.",
    "dos": "Games for MS-DOS and IBM PC compatible computers.",
    "prboom": "PrBoom+, a port of id Software's Doom (1993) engine, with the original WADs.",
    "eduke32": "EDuke32, a port of the Build engine of 3D Realms' Duke Nukem 3D (1996).",
    "pico8": "Fantasy console: 128×128 pixels and 16 colors; each game fits in a PNG image.",
    "ports": "Native games without an emulator: PortMaster and ports like Cave Story or GZDoom.",
    "tools": "Tools available on this installation.",
    "emulators": "Emulators available on this installation.",
    "imageviewer": "Screenshots saved on this console.",
}

# Layout that depends on a word's width, per language: key -> {lang: value}
GEO = {}


def t(key):
    """The variable an element uses for one of TEXT's words."""
    if key not in TEXT:
        raise KeyError(key)
    return "${tx." + key + "}"


def word(key, lang):
    return TEXT[key][0 if lang == SPANISH else 1]


def geo(key, values):
    """Register a per-language layout value ({"es": ..., "en": ...}) and return its variable. A key names one
    value: registering it again with others is a mistake."""
    if GEO.setdefault(key, values) != values:
        raise ValueError("two layouts for " + key)
    return "${tx." + key + "}"


DATES = {}


def written_date(binding):
    """The variable holding a date binding written in each language's order."""
    key = "date." + binding.strip("{}").replace(":", ".")
    DATES[key] = binding
    return "${tx." + key + "}"


def blocks(lang):
    """Every tx.* value for one language."""
    i = 0 if lang == SPANISH else 1
    values = {"tx." + k: v[i] for k, v in TEXT.items()}
    values.update({"tx." + k: v["es" if lang == SPANISH else "en"] for k, v in GEO.items()})
    values.update({"tx." + k: DATE[i].replace("{d}", b) for k, b in DATES.items()})
    return values


def add_text_variables(root):
    """Both languages' tx.* variables at the top of theme.xml: ES reads a file's own variables before its
    subsets, whose names use them. English first, then Spanish for a Spanish console."""
    first = 1 if root.find("formatVersion") is not None else 0
    for offset, (lang, attrs) in enumerate((("en", {}), (SPANISH, {"lang": SPANISH}))):
        block = ET.Element("variables", attrs)
        for k, v in blocks(lang).items():
            ET.SubElement(block, k).text = v
        root.insert(first + offset, block)


def localized(parent, spanish, english, **attrs):
    """Variables whose values differ by language: English by default, then the Spanish ones that differ."""
    block = ET.SubElement(parent, "variables", attrs)
    for k, v in english.items():
        ET.SubElement(block, k).text = v
    changed = {k: v for k, v in spanish.items() if english.get(k) != v}
    if changed:
        block = ET.SubElement(parent, "variables", {**attrs, "lang": SPANISH})
        for k, v in changed.items():
            ET.SubElement(block, k).text = v
