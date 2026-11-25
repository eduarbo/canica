"""The game switcher (FN + SELECT, or Extras > Continuar): the custom view «switcher».

Its left column is the game list's own (games.details_column), bound to the game shown, with
A to continue in place of X. On the right, the picture of the game's automatic save inside
switcherShot, with the theme's corners; above it, switcherState says when that save was made;
under it, one dot per game around switcherDot. The frontend fills switcherState, places the
picture and draws the dots; every other element is an extra it binds to the game.
"""
from xml.etree import ElementTree as ET

from games import details_column
from layout import ART, LOOK, element, image, prop, text


def data_only(node):
    node.attrib.pop("extra", None)
    return node


def game_switcher(root):
    v = ET.SubElement(root, "customView", {"name": "switcher"})
    element(v, "image", "background", {"path": LOOK + "canvas.png", "pos": "0 0", "size": "1 1", "zIndex": "0"})
    image(v, "detailsPanel", 0, 31, 200, 449, LOOK + "panel.png", z=1)
    # The header of the home screen, with this screen's name where the brand is
    image(v, "headerBand", 0, 0, 640, 31, LOOK + "top.png", z=51)
    image(v, "brandMark", 11, 6, 19, 19, LOOK + "canica.png", z=62)
    text(v, "library", 35, 6, 172, 19, "CONTINUAR", 12, color="${accent}", weight="Black", z=62)
    # Without the keys that change console: here L1 and R1 turn the games, under the picture
    details_column(v, None, [("", "Continuar", "!{game:folder}")], action_key="a.png")

    data_only(text(v, "switcherState", 214, 36, 412, 24, "", 11.5, weight="Bold", align="center", z=40))
    shot = data_only(image(v, "switcherShot", 214, 70, 412, 376, ART + "empty.png", z=30))
    prop(shot, "roundCorners", "${tileRadius}")
    image(v, "switcherPrevKey", 214, 454, 26, 18, ART + "l1.png", z=35)
    image(v, "switcherNextKey", 600, 454, 26, 18, ART + "r1.png", z=35)
    data_only(text(v, "switcherDot", 420, 462, 11, 5, "", 10, color="${rail}", z=35))
    data_only(text(v, "switcherDotOn", 420, 462, 11, 5, "", 10, color="${accent}", z=35))
