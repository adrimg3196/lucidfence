#!/usr/bin/env python3
"""Cartelas del anuncio YC-style para LucidFence. Paleta oficial.
Cada cartela -> PNG 1280x704 para luego convertir a mp4 (CinematicRenderer)."""
from PIL import Image, ImageDraw, ImageFilter
import os

W, H = 1280, 704
VIOLET = (124, 130, 255)
MINT = (73, 213, 156)
AMBER = (240, 188, 94)
DARK = (9, 11, 15)
LIGHT = (233, 237, 245)

FONT_DIR = "/Library/Fonts"
F_REG = os.path.join(FONT_DIR, "Arial.ttf")
F_BOLD = os.path.join(FONT_DIR, "Arial Bold.ttf")

def font(sz, bold=False):
    p = F_BOLD if bold else F_REG
    if not os.path.exists(p):
        p = F_REG if os.path.exists(F_REG) else None
    from PIL import ImageFont
    return ImageFont.truetype(p, sz) if p else ImageFont.load_default()

def vgrad(top, bottom):
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img

def wrap(text, fnt, maxw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if fnt.getlength(test) <= maxw:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def card(path, title, subtitle, accent, kicker=None):
    img = vgrad((14, 16, 24), DARK)
    d = ImageDraw.Draw(img)
    # glow esquina
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -200, 520, 520], fill=(*accent, 40))
    img = img.convert("RGBA"); img.alpha_composite(glow); img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    x = 90
    if kicker:
        d.text((x, 120), kicker.upper(), font=font(30, True), fill=accent)
    lines = wrap(title, font(58, True), W - 2 * x)
    y = 230 if not kicker else 180
    for ln in lines:
        d.text((x, y), ln, font=font(58, True), fill=LIGHT); y += 70
    if subtitle:
        sl = wrap(subtitle, font(34), W - 2 * x)
        y = 470
        for ln in sl:
            d.text((x, y), ln, font=font(34), fill=(160, 168, 185)); y += 46
    img.save(path)
    print(path)

OUT = os.path.dirname(os.path.abspath(__file__))
card(f"{OUT}/c1.png", "Tu flota se mueve.\n¿Tu seguridad también?",
     "Cada equipo fuera de zona es riesgo invisible.", VIOLET, kicker="El riesgo")
card(f"{OUT}/c2.png", "Lo que sale de tu zona\nqueda aislado",
     "LucidFence dibuja el perímetro y separa lo no confiable.", MINT, kicker="Qué hace")
card(f"{OUT}/c3.png", "Conéctalo en 3 clics",
     "Applivery · Intune · Jamf · Hexnode · Fleetsmith. Un solo perímetro.", VIOLET, kicker="Cómo conectar")
card(f"{OUT}/end.png", "LucidFence",
     "Geofencing + UEM · autónomo y local-first · Ahora disponible", MINT, kicker="Lanzamiento")
