"""Vyrobí kocka.ico (spící kočičí hlava) pro Windows build. Potřebuje Pillow."""
import sys

from PIL import Image, ImageDraw

ORANGE = (255, 175, 95, 255)
DARK = (60, 40, 30, 255)
S = 256


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # uši
    d.polygon([(40, 120), (60, 20), (120, 80)], fill=ORANGE)
    d.polygon([(216, 120), (196, 20), (136, 80)], fill=ORANGE)
    # hlava
    d.ellipse([28, 60, 228, 240], fill=ORANGE)
    # zavřená oči (spí)
    d.arc([62, 128, 118, 168], 20, 160, fill=DARK, width=10)
    d.arc([138, 128, 194, 168], 20, 160, fill=DARK, width=10)
    # čumák a pusa
    d.polygon([(118, 176), (138, 176), (128, 188)], fill=DARK)
    d.arc([104, 180, 130, 206], 20, 160, fill=DARK, width=6)
    d.arc([126, 180, 152, 206], 20, 160, fill=DARK, width=6)
    return img


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "kocka.ico"
    img = draw()
    if out.endswith(".ico"):
        img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    else:
        img.save(out)
