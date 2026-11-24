"""Render original sample media and a disposable GBA catalogue for release previews."""
import math
import random
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

TITLES = ("Órbita de Cobre", "Marea de Cristal", "Noche en el Observatorio",
          "Jardines de Sal", "Bosque de las Lunas", "Expreso al Horizonte", "La Última Baliza")
PALETTES = (
    ("1d193e", "77416b", "e59458", "fff0a8", "231d33", "e85e48"),
    ("113659", "427d97", "84d2c3", "e1f9d6", "172e51", "f39962"),
    ("232345", "614575", "b07bb3", "f9cf8b", "282340", "87d3bf"),
    ("535557", "be8669", "f1cba0", "fff1cb", "513f41", "813b50"),
    ("0f343a", "30716a", "8db582", "f9e6ab", "193947", "edb07b"),
    ("292747", "a65272", "ffa465", "fce7a8", "382b46", "75b8bf"),
    ("171d35", "43446d", "a57395", "f7ceb3", "202943", "e86759"),
)


def scene(index):
    rng = random.Random(index + 5)
    colors = ["#" + c for c in PALETTES[index]]
    im = Image.new("RGB", (180, 106), colors[0])
    d = ImageDraw.Draw(im)
    for i in range(4):
        d.rectangle((0, 18 + 12*i, 179, 105), fill=colors[min(2, (i + 1)//2)])
    x = (107, 36, 112, 72, 116, 43, 124)[index]
    d.ellipse((x-17, 8, x+17, 42), fill=colors[3])
    if index % 2 == 0:
        d.line((x-25, 33, x+25, 16), fill=colors[2], width=2)
    for _ in range(22):
        sx, sy = rng.randrange(180), rng.randrange(5, 38)
        if abs(sx-x) > 24:
            d.point((sx, sy), fill=colors[3])
    for layer, base in enumerate((57, 73, 86)):
        points = [(x, base + int(7*math.sin(x/15 + index + layer)) + rng.randrange(-5, 6))
                  for x in range(-5, 190, 7)]
        d.polygon(points + [(190, 110), (-5, 110)], fill=(colors[1], colors[4], colors[0])[layer])
    if index in (0, 2, 6):
        d.polygon([(52, 66), (56, 47), (60, 47), (65, 66)], fill=colors[4])
        d.ellipse((50, 38, 66, 54), fill=colors[4])
        d.rectangle((53, 44, 63, 46), fill=colors[3])
        d.line((59, 38, 61, 32), fill=colors[3])
    else:
        for x in range(12, 180, 33):
            y = 62 + rng.randrange(8)
            d.polygon([(x, y-12), (x-5, y), (x+5, y)], fill=colors[4])
    for _ in range(27):
        sx, sy = rng.randrange(180), rng.randrange(83, 106)
        d.line((sx, sy, sx + rng.randrange(1, 4), sy), fill=colors[1])
    return im.resize((540, 318), Image.Resampling.NEAREST)


def create(root):
    roms = root / "roms/gba"
    if roms.exists():
        raise SystemExit("Usa un directorio de muestra nuevo")
    art = roms / "images"
    art.mkdir(parents=True)
    games = ET.Element("gameList")
    for index, title in enumerate(TITLES):
        filename = f"{index+1:02d}"
        (roms / (filename+".gba")).touch()
        scene(index).save(art / (filename+".png"))
        game = ET.SubElement(games, "game")
        for key, value in {"path":f"./{filename}.gba", "name":title,
                           "image":f"./images/{filename}.png", "thumbnail":f"./images/{filename}.png",
                           "developer":"Taller Lunar", "releasedate":"20040615T000000", "players":"1",
                           "genre":("Exploración","Aventura","Puzle","Estrategia","Aventura","Carreras","Plataformas")[index],
                           "rating":str((88,76,94,68,85,91,79)[index]/100), "favorite":"true" if index%2==0 else "false",
                           "playcount":str(index+2), "lastplayed":f"202611{10+index:02d}T172500", "gametime":str(75*(index+1)),
                           "desc":"La marea descubre un paso entre las islas. Sigue las luces hasta el observatorio antes de que vuelva el agua."}.items():
            ET.SubElement(game, key).text=value
    ET.ElementTree(games).write(roms / "gamelist.xml", encoding="utf-8")


if __name__ == "__main__":
    create(Path(sys.argv[1]))
