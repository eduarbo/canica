"""The game switcher (FN + SELECT): elements of the screen view that the frontend reads, not extras.

It looks like a game's sheet: the left panel with the title, the counters and the action, and the
picture of the automatic save on the right, with the tiles' corners. The frontend fills the texts,
places the picture inside switcherShot and draws one dot per game around switcherDot's position.
"""
from layout import ART, DISPLAY_FONT, LOOK, image, prop, text


def data_only(node):
    node.attrib.pop("extra", None)
    return node


def counter(v, name, left, top, width, icon, inset):
    size = 15
    x = left + inset
    data_only(image(v, "switcher" + name + "Icon", x, top + 1, size, size, LOOK + "metric-" + icon + ".png", z=32))
    data_only(text(v, "switcher" + name, x + size + 3, top, width + left - x - size - 3, 18, "", 15, weight="Black", z=33))
    data_only(text(v, "switcher" + name + "Label", left, top + 17, width, 13, "", 10, color="${muted}", align="center", z=33))


def game_switcher(v):
    background = data_only(text(v, "switcherBackground", 0, 0, 640, 480, "", 12, z=1))
    prop(background, "backgroundColor", "${canvas}")
    data_only(image(v, "switcherHeader", 0, 0, 640, 31, LOOK + "top.png", z=3))
    data_only(image(v, "switcherBrand", 11, 6, 19, 19, LOOK + "canica.png", z=40))
    data_only(text(v, "switcherHeading", 35, 6, 172, 19, "CONTINUAR", 12, color="${accent}", weight="Black", z=40))
    data_only(image(v, "switcherPanel", 0, 31, 200, 449, LOOK + "panel.png", z=2))

    system = data_only(text(v, "switcherSystem", 15, 40, 172, 22, "", 14, color="${muted}", align="center", weight="Black", z=33))
    system.find("fontPath").text = DISPLAY_FONT
    name = data_only(text(v, "switcherName", 15, 74, 172, 92, "", 23, weight="ExtraBold", wrap=True, z=33))
    name.find("fontPath").text = DISPLAY_FONT
    name.find("lineSpacing").text = "0.94"
    prop(name, "forceUppercase", "false")
    prop(name, "autoScroll", "vertical")

    data_only(image(v, "switcherBand", 5, 178, 190, 40, LOOK + "metric-band.png", z=31))
    counter(v, "Plays", 5, 183, 88, "played", 12)
    counter(v, "Time", 93, 183, 102, "time", 8)

    data_only(text(v, "switcherLastLabel", 15, 232, 80, 16, "", 11, color="${muted}", z=33))
    data_only(text(v, "switcherLast", 86, 231, 101, 18, "", 12, weight="Bold", align="right", z=33))
    data_only(text(v, "switcherStateLabel", 15, 258, 172, 16, "", 11, color="${muted}", z=33))
    data_only(text(v, "switcherState", 15, 276, 172, 18, "", 12, weight="Bold", z=33))

    data_only(text(v, "switcherDescription", 15, 304, 172, 104, "", 11.5, weight="Regular", color="${muted}",
                   wrap=True, scroll=True, z=33))

    # The action, as on a game's sheet: the lit button with the key that does it
    data_only(image(v, "switcherAction", 13, 420, 174, 31, LOOK + "cta.png", z=32))
    data_only(image(v, "switcherActionKey", 62, 428, 16, 15, LOOK + "a.png", z=34))
    data_only(text(v, "switcherActionLabel", 83, 420, 100, 31, "", 13, color="${ctaInk}", weight="ExtraBold", z=34))

    shot = data_only(image(v, "switcherShot", 214, 43, 412, 400, ART + "empty.png", z=30))
    prop(shot, "roundCorners", "${tileRadius}")

    # The pager along the bottom, between the shoulder buttons that also turn it
    data_only(image(v, "switcherPrevKey", 214, 454, 26, 18, ART + "l1.png", z=35))
    data_only(image(v, "switcherNextKey", 600, 454, 26, 18, ART + "r1.png", z=35))
    data_only(text(v, "switcherDot", 420, 463, 11, 5, "", 10, color="${rail}", z=35))
    data_only(text(v, "switcherDotOn", 420, 463, 11, 5, "", 10, color="${accent}", z=35))
