#!/usr/bin/env python3
"""Genera brand/logo_overlay.png: escudo LucidFence fiel al SVG oficial,
sobre transparente para overlay con fade en el spot FLUX 3."""
from PIL import Image, ImageDraw
import math

def point_in_poly(x, y, poly):
    n = len(poly); inside = False; j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

def shield_poly():
    pts = [(256, 72), (112, 132), (112, 237)]
    for t in [i / 12 for i in range(1, 13)]:
        x = 112 + (256 - 112) * t
        y = 237 + (440 - 237) * (t ** 1.5)
        pts.append((int(x), int(y)))
    for t in [i / 12 for i in range(1, 13)]:
        x = 400 - (400 - 256) * t
        y = 237 + (440 - 237) * (t ** 1.5)
        pts.append((int(x), int(y)))
    pts += [(400, 237), (400, 132)]
    return pts

poly = shield_poly()
minx = min(p[0] for p in poly); maxx = max(p[0] for p in poly)
miny = min(p[1] for p in poly); maxy = max(p[1] for p in poly)
for y in range(miny, maxy + 1):
    f = (y - miny) / (maxy - miny) if maxy > miny else 0
    r = int(0x90 + (0x5c - 0x90) * f)
    g = int(0x95 + (0x62 - 0x95) * f)
    b = int(0xff + (0xe8 - 0xff) * f)
    row = [(x, y) for x in range(S) if point_in_poly(x, y, poly)]
    if row:
        d.point(row, fill=(r, g, b, 255))

def thick_line(a, b, w, color):
    steps = int(math.hypot(b[0] - a[0], b[1] - a[1]))
    for i in range(steps + 1):
        t = i / steps
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        d.ellipse([x - w/2, y - w/2, x + w/2, y + w/2], fill=color)

thick_line((190, 255), (232, 297), 34, (255, 255, 255, 255))
thick_line((232, 297), (321, 184), 34, (255, 255, 255, 255))

img = img.resize((256, 256), Image.Resampling.LANCZOS)
img.save("logo_overlay.png")
print("logo_overlay.png", img.size)
