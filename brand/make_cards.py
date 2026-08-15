#!/usr/bin/env python3
"""Genera title.png y endcard.png (branding LucidFence) para el montaje
estilo OpenMontage: narrativa + marca + proveedor. 1280x704, 24fps."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1280, 704
OUT = os.path.dirname(os.path.abspath(__file__))

def font(sz):
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/SFNS.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

def vgrad(height, top=(0x09,0x0b,0x0f), bot=(0x12,0x16,0x1d)):
    base = Image.new("RGB", (1, height))
    px = base.load()
    for y in range(height):
        f = y/(height-1)
        px[0,y] = tuple(int(t+(b-t)*f) for t,b in zip(top,bot))
    return base.resize((W, height))

def draw_logo(d, cx, cy, s=70):
    # escudo violeta + check (mismo que make_logo, compacto)
    poly = [(cx, cy-s), (cx-s*0.7, cy-s*0.6), (cx-s*0.7, cy-s*0.1)]
    for t in [i/12 for i in range(1,13)]:
        poly.append((int(cx-s*0.7+(cx-cx+s*0.7)*t), int(cy-s*0.1+(s*0.95)*(t**1.5))))
    for t in [i/12 for i in range(1,13)]:
        poly.append((int(cx+s*0.7-(s*0.7)*t), int(cy-s*0.1+(s*0.95)*(t**1.5))))
    poly += [(cx+s*0.7, cy-s*0.1), (cx+s*0.7, cy-s*0.6)]
    d.polygon(poly, fill=(0x7c,0x82,0xff))
    # check
    for (a,b) in [((cx-s*0.32,cy-s*0.02),(cx-s*0.12,cy+s*0.16)),((cx-s*0.12,cy+s*0.16),(cx+s*0.34,cy-s*0.22))]:
        steps=int(((b[0]-a[0])**2+(b[1]-a[1])**2)**0.5)
        for i in range(steps+1):
            t=i/steps; x=a[0]+(b[0]-a[0])*t; y=a[1]+(b[1]-a[1])*t
            d.ellipse([x-9,y-9,x+9,y+9], fill=(255,255,255))

def glow_text(d, xy, text, fnt, fill, glow=(0x7c,0x82,0xff)):
    x,y=xy
    for dx,dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,2)]:
        d.text((x+dx,y+dy), text, font=fnt, fill=glow+(0,))
    d.text((x,y), text, font=fnt, fill=fill)

# --- TITLE ---
im = Image.new("RGB", (W,H), (9,11,15))
im.paste(vgrad(H), (0,0))
d = ImageDraw.Draw(im)
draw_logo(d, W//2, 250, s=78)
glow_text(d, (W//2-330, 360), "LUCIDFENCE", font(86), (245,247,250))
glow_text(d, (W//2-360, 470), "The perimeter that thinks", font(38), (146,153,168))
im.save(f"{OUT}/title.png"); print("title.png")

# --- END CARD ---
im = Image.new("RGB", (W,H), (9,11,15))
im.paste(vgrad(H), (0,0))
d = ImageDraw.Draw(im)
draw_logo(d, W//2, 210, s=64)
glow_text(d, (W//2-330, 300), "LUCIDFENCE", font(72), (245,247,250))
glow_text(d, (W//2-300, 392), "Geofencing + UEM  ·  autonomous & local-first", font(30), (73,213,156))
glow_text(d, (W//2-260, 470), "Made with FLUX 3  ·  @NousResearch @bfl_ai", font(28), (146,153,168))
im.save(f"{OUT}/endcard.png"); print("endcard.png")
