"""Stylised premises 'photos' (PIL vector-ish illustrations, 1400x1000 JPEG) with readable signage."""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from profiles import font, save_jpg, text_size, watermark

W, H = 1400, 1000


def _gradient(img, top, bottom, y0=0, y1=None):
    y1 = H if y1 is None else y1
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([0, y, W, y], fill=col)


def _finish(img: Image.Image, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
    vig = 1.0 - 0.28 * np.clip(dist - 0.5, 0, 1)
    arr *= vig[..., None]
    arr += rng.normal(0, 3.2, arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return out.filter(ImageFilter.GaussianBlur(0.4))


def _sign(d, box, text, bg, fg, border=None, size=None, fnt="sans_black"):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=10, fill=bg, outline=border or fg, width=5)
    size = size or int((y1 - y0) * 0.55)
    f = font(fnt, size)
    tw, th = text_size(d, text, f)
    while tw > (x1 - x0) - 40 and size > 12:
        size -= 2
        f = font(fnt, size)
        tw, th = text_size(d, text, f)
    bb = d.textbbox((0, 0), text, font=f)
    d.text(((x0 + x1) / 2 - tw / 2 - bb[0], (y0 + y1) / 2 - th / 2 - bb[1]), text, font=f, fill=fg)


def draw_car(d, x, y, w, color, facing=1):
    """Side view car; (x, y) = bottom-left of the body, w = length."""
    h = w * 0.30
    wheel_r = w * 0.085
    body = [(x, y - h * 0.15), (x, y - h * 0.65), (x + w * 0.18, y - h * 0.7), (x + w * 0.30, y - h * 1.15),
            (x + w * 0.68, y - h * 1.15), (x + w * 0.82, y - h * 0.7), (x + w, y - h * 0.6), (x + w, y - h * 0.15)]
    d.polygon(body, fill=color, outline=tuple(max(0, c - 60) for c in color))
    # windows
    d.polygon([(x + w * 0.33, y - h * 1.08), (x + w * 0.47, y - h * 1.08), (x + w * 0.47, y - h * 0.74), (x + w * 0.22, y - h * 0.74)],
              fill=(190, 215, 230))
    d.polygon([(x + w * 0.50, y - h * 1.08), (x + w * 0.66, y - h * 1.08), (x + w * 0.78, y - h * 0.74), (x + w * 0.50, y - h * 0.74)],
              fill=(190, 215, 230))
    for cx in (x + w * 0.22, x + w * 0.78):
        d.ellipse([cx - wheel_r, y - wheel_r * 1.05, cx + wheel_r, y + wheel_r * 0.95], fill=(30, 30, 30))
        d.ellipse([cx - wheel_r * 0.5, y - wheel_r * 0.55, cx + wheel_r * 0.5, y + wheel_r * 0.45], fill=(170, 170, 170))
    d.rectangle([x + w * 0.96, y - h * 0.55, x + w, y - h * 0.4], fill=(255, 240, 150))
    d.rectangle([x, y - h * 0.55, x + w * 0.04, y - h * 0.4], fill=(220, 50, 50))


def draw_lift(d, x, y, w):
    """Two-post lift with the platform arms at height y, posts around it."""
    d.rectangle([x - 30, y - 300, x - 6, y + 160], fill=(80, 90, 120))
    d.rectangle([x + w + 6, y - 300, x + w + 30, y + 160], fill=(80, 90, 120))
    d.rectangle([x - 10, y + 2, x + w + 10, y + 16], fill=(120, 130, 150))
    d.rectangle([x - 10, y + 24, x + w * 0.35, y + 40], fill=(110, 115, 130))
    d.rectangle([x + w * 0.65, y + 24, x + w + 10, y + 40], fill=(110, 115, 130))


def _shelf_goods(d, r, box, rows=3, cols=10):
    x0, y0, x1, y1 = box
    rh = (y1 - y0) / rows
    cw = (x1 - x0) / cols
    palette = [(220, 60, 60), (240, 180, 40), (60, 140, 80), (60, 110, 200), (230, 120, 50), (200, 200, 200), (140, 70, 160)]
    for i in range(rows):
        sy = y0 + rh * (i + 1)
        d.rectangle([x0, sy - 6, x1, sy], fill=(150, 110, 70))
        for j in range(cols):
            col = r.choice(palette)
            gw = cw * r.uniform(0.55, 0.85)
            gh = rh * r.uniform(0.45, 0.8)
            gx = x0 + cw * j + (cw - gw) / 2
            d.rectangle([gx, sy - 6 - gh, gx + gw, sy - 6], fill=col, outline=tuple(max(0, c - 50) for c in col))


def premises_warung(seed: int, variant: int, out: Path):
    r = random.Random(seed)
    img = Image.new("RGB", (W, H), (200, 220, 240))
    d = ImageDraw.Draw(img)
    if variant == 1:
        _gradient(img, (135, 185, 235), (215, 230, 245), 0, 560)
        _gradient(img, (150, 150, 145), (110, 110, 105), 560, H)
        d = ImageDraw.Draw(img)
        # neighbouring walls
        d.rectangle([0, 200, 180, 600], fill=(205, 190, 170))
        d.rectangle([1220, 200, W, 600], fill=(190, 200, 180))
        # building
        d.rectangle([180, 160, 1220, 620], fill=(238, 226, 200))
        d.rectangle([180, 160, 1220, 180], fill=(170, 60, 50))
        # awning stripes
        for i, x in enumerate(range(180, 1220, 65)):
            d.polygon([(x, 290), (x + 65, 290), (x + 85, 370), (x + 20, 370)], fill=(200, 50, 50) if i % 2 == 0 else (245, 245, 240))
        d.rectangle([180, 362, 1240, 394], fill=(160, 40, 40))
        tag = "Sembako • Minuman • Pulsa • Gas & Galon"
        tw, _ = text_size(d, tag, font("sans_bold", 21))
        d.text((710 - tw / 2, 366), tag, font=font("sans_bold", 21), fill=(255, 245, 225))
        # sign
        _sign(d, (240, 195, 1160, 285), "WARUNG IBU SARI", (250, 205, 50), (140, 30, 30))
        # open front with shelves
        d.rectangle([230, 394, 1170, 620], fill=(70, 55, 45))
        _shelf_goods(d, r, (250, 405, 760, 600), rows=4, cols=12)
        _shelf_goods(d, r, (790, 405, 1150, 600), rows=4, cols=8)
        # counter
        d.rectangle([600, 540, 1000, 625], fill=(120, 80, 50))
        d.rectangle([600, 540, 1000, 552], fill=(160, 110, 70))
        # hanging snack strips
        for x in range(260, 560, 40):
            d.line([x, 394, x, 500], fill=(230, 230, 230), width=2)
            for yy in range(405, 500, 24):
                d.rectangle([x - 10, yy, x + 10, yy + 16], fill=r.choice([(230, 70, 70), (70, 170, 90), (240, 190, 60), (60, 120, 220)]))
        # gas cylinders and gallon bottles
        for i in range(4):
            d.rounded_rectangle([1030 + i * 38, 560, 1058 + i * 38, 630], radius=8, fill=(40, 140, 80))
        for i in range(3):
            d.rounded_rectangle([200 + i * 36, 575, 228 + i * 36, 635], radius=10, fill=(120, 180, 230))
        # bench + plant
        d.rectangle([1250, 560, 1390, 580], fill=(110, 75, 45))
        d.rectangle([1260, 580, 1270, 640], fill=(90, 60, 35))
        d.rectangle([1370, 580, 1380, 640], fill=(90, 60, 35))
        d.ellipse([40, 480, 150, 600], fill=(70, 140, 70))
        d.rectangle([80, 590, 110, 660], fill=(120, 80, 50))
        # pavement line
        d.rectangle([0, 640, W, 660], fill=(190, 185, 175))
        d.rectangle([0, 660, W, 680], fill=(210, 205, 195))
    else:
        # interior: shelves wall + counter + small sign
        _gradient(img, (240, 236, 225), (225, 218, 205), 0, 600)
        _gradient(img, (180, 170, 150), (120, 112, 100), 600, H)
        d = ImageDraw.Draw(img)
        d.rectangle([60, 120, 1340, 640], fill=(120, 85, 55))
        _shelf_goods(d, r, (80, 140, 1320, 630), rows=5, cols=26)
        _sign(d, (480, 40, 920, 110), "WARUNG IBU SARI", (250, 205, 50), (140, 30, 30), size=34)
        # freezer / cooler
        d.rectangle([1120, 420, 1360, 760], fill=(80, 130, 200), outline=(50, 90, 150), width=4)
        d.rectangle([1140, 440, 1340, 600], fill=(200, 230, 250))
        d.text((1170, 700), "DINGIN", font=font("sans_bold", 30), fill="white")
        # counter with jars
        d.rectangle([100, 640, 1050, 820], fill=(140, 95, 60))
        d.rectangle([100, 640, 1050, 660], fill=(175, 125, 80))
        for i in range(9):
            x = 150 + i * 95
            d.rounded_rectangle([x, 560, x + 60, 640], radius=12, fill=(230, 230, 220), outline=(150, 150, 140), width=2)
            d.rectangle([x + 10, 590, x + 50, 630], fill=r.choice([(220, 120, 60), (200, 60, 60), (240, 200, 80)]))
        # cash tray + QR standee
        d.rectangle([840, 575, 980, 640], fill=(50, 50, 55))
        d.rectangle([860, 520, 960, 575], fill="white", outline=(30, 30, 30), width=3)
        for yy in range(528, 568, 8):
            for xx in range(868, 952, 8):
                if r.random() < 0.5:
                    d.rectangle([xx, yy, xx + 6, yy + 6], fill=(20, 20, 20))
        d.text((868, 578), "QRIS", font=font("sans_bold", 18), fill=(240, 240, 240))
    img = _finish(img, seed)
    img = watermark(img)
    save_jpg(img, out)


def premises_stockroom(seed: int, out: Path):
    r = random.Random(seed)
    img = Image.new("RGB", (W, H), (235, 230, 225))
    _gradient(img, (240, 236, 232), (222, 215, 208), 0, 620)
    d = ImageDraw.Draw(img)
    # wooden floor
    for i, y in enumerate(range(620, H, 38)):
        d.rectangle([0, y, W, y + 38], fill=(190, 150, 110) if i % 2 == 0 else (178, 140, 100))
        d.line([0, y, W, y], fill=(150, 110, 75), width=2)
    # window
    d.rectangle([1040, 120, 1340, 420], fill=(200, 225, 245), outline=(240, 240, 240), width=14)
    d.line([1190, 120, 1190, 420], fill=(240, 240, 240), width=10)
    d.line([1040, 270, 1340, 270], fill=(240, 240, 240), width=10)
    # sign on the wall
    d.rounded_rectangle([520, 60, 900, 150], radius=14, fill=(255, 228, 236), outline=(220, 90, 130), width=5)
    f = font("hand2", 54, index=1)
    tw, th = text_size(d, "Linh Fashion", f)
    d.text((710 - tw / 2, 72), "Linh Fashion", font=f, fill=(200, 50, 100))
    # clothing racks
    palette = [(230, 90, 120), (90, 130, 210), (250, 210, 90), (120, 190, 140), (240, 240, 240), (60, 60, 70), (200, 140, 200), (240, 150, 90)]
    for rx in (80, 560):
        d.rectangle([rx, 250, rx + 12, 640], fill=(80, 80, 85))
        d.rectangle([rx + 400, 250, rx + 412, 640], fill=(80, 80, 85))
        d.rectangle([rx, 250, rx + 412, 262], fill=(90, 90, 95))
        d.rectangle([rx - 30, 630, rx + 60, 644], fill=(80, 80, 85))
        d.rectangle([rx + 360, 630, rx + 445, 644], fill=(80, 80, 85))
        x = rx + 20
        while x < rx + 380:
            col = r.choice(palette)
            gw = r.randint(34, 50)
            gl = r.randint(220, 330)
            d.polygon([(x + gw / 2, 262), (x + gw / 2 - 12, 282), (x + gw / 2 + 12, 282)], outline=(60, 60, 60), width=2)
            d.polygon([(x, 290), (x + gw, 290), (x + gw + 8, 330), (x + gw, 332), (x + gw, 282 + gl), (x, 282 + gl), (x, 332), (x - 8, 330)],
                      fill=col, outline=tuple(max(0, c - 45) for c in col))
            x += gw + r.randint(8, 16)
    # boxes
    for i, (bx, by, bw, bh) in enumerate([(1050, 500, 170, 130), (1070, 380, 140, 120), (1240, 520, 130, 110), (1090, 650, 180, 120), (1260, 640, 120, 130)]):
        d.rectangle([bx, by, bx + bw, by + bh], fill=(205, 165, 110), outline=(150, 110, 60), width=3)
        d.rectangle([bx + bw / 2 - 12, by, bx + bw / 2 + 12, by + bh], fill=(225, 200, 150))
        d.text((bx + 12, by + 10), r.choice(["GHN", "J&T", "FRAGILE", "SIZE M", "AO THUN"]), font=font("sans_bold", 16), fill=(90, 60, 30))
    # desk with laptop and parcels
    d.rectangle([160, 700, 700, 730], fill=(230, 230, 228))
    d.rectangle([180, 730, 200, 900], fill=(200, 200, 200))
    d.rectangle([660, 730, 680, 900], fill=(200, 200, 200))
    d.polygon([(300, 700), (460, 700), (470, 600), (310, 600)], fill=(60, 60, 65))
    d.polygon([(312, 692), (458, 692), (466, 608), (318, 608)], fill=(120, 180, 240))
    d.rectangle([280, 690, 480, 700], fill=(90, 90, 95))
    for i in range(3):
        d.rectangle([520 + i * 10, 640 - i * 22, 640 + i * 10, 700 - i * 22], fill=(236, 236, 236), outline=(180, 180, 180), width=2)
    # mannequin
    d.ellipse([920, 300, 980, 360], fill=(235, 225, 215))
    d.polygon([(905, 370), (995, 370), (1010, 560), (890, 560)], fill=(230, 90, 120))
    d.rectangle([944, 560, 956, 700], fill=(120, 120, 120))
    d.ellipse([900, 690, 1000, 720], fill=(90, 90, 90))
    img = _finish(img, seed)
    img = watermark(img)
    save_jpg(img, out)


def premises_garage(seed: int, out: Path):
    r = random.Random(seed)
    img = Image.new("RGB", (W, H), (200, 220, 240))
    _gradient(img, (120, 170, 225), (210, 225, 240), 0, 560)
    _gradient(img, (120, 120, 118), (85, 85, 82), 560, H)
    d = ImageDraw.Draw(img)
    # building
    d.rectangle([120, 150, 1280, 620], fill=(215, 215, 210))
    d.rectangle([120, 150, 1280, 172], fill=(60, 70, 90))
    # bay opening
    d.rectangle([200, 330, 1000, 620], fill=(45, 45, 52))
    # roller door track
    for y in range(330, 400, 12):
        d.line([200, y, 1000, y], fill=(90, 90, 100), width=3)
    # lift + car inside bay
    draw_lift(d, 360, 520, 480)
    draw_car(d, 360, 520, 480, (200, 60, 50))
    # mechanic silhouette
    d.ellipse([270, 455, 300, 485], fill=(40, 40, 45))
    d.rectangle([272, 485, 298, 560], fill=(40, 60, 120))
    d.rectangle([270, 560, 282, 620], fill=(40, 40, 45))
    d.rectangle([288, 560, 300, 620], fill=(40, 40, 45))
    # sign board with car silhouette
    _sign(d, (180, 195, 1020, 305), "REYES AUTO REPAIR", (25, 40, 80), (250, 200, 40), size=70)
    # car silhouette icon on sign
    draw_car(d, 1060, 286, 180, (250, 200, 40))
    d.rectangle([1040, 195, 1260, 305], outline=(250, 200, 40), width=5)
    d.text((1052, 200), "SERVICE", font=font("sans_bold", 20), fill=(250, 200, 40))
    d.text((200, 307), "Change Oil • Brakes • Aircon • Tune-up • Underchassis", font=font("sans_bold", 18), fill=(50, 60, 80))
    # side wall: tyres, drum, shelves
    for i, (tx, ty) in enumerate([(1080, 540), (1080, 480), (1080, 420), (1160, 540), (1160, 480)]):
        d.ellipse([tx, ty, tx + 70, ty + 70], fill=(30, 30, 30))
        d.ellipse([tx + 22, ty + 22, tx + 48, ty + 48], fill=(150, 150, 150))
    d.rectangle([1200, 480, 1260, 610], fill=(40, 90, 170))
    d.text((1208, 530), "OIL", font=font("sans_bold", 18), fill="white")
    # road & kerb
    d.rectangle([0, 620, W, 650], fill=(170, 165, 150))
    for x in range(0, W, 120):
        d.rectangle([x, 820, x + 60, 832], fill=(230, 220, 120))
    # second car waiting outside
    draw_car(d, 60, 780, 420, (80, 110, 200))
    # tree
    d.rectangle([1330, 380, 1355, 640], fill=(100, 70, 40))
    d.ellipse([1260, 240, 1400, 420], fill=(70, 140, 70))
    img = _finish(img, seed)
    img = watermark(img)
    save_jpg(img, out)


def premises_workshop_interior(seed: int, out: Path):
    """Interior shot with no business name (used for the past-case reuse trap T20)."""
    r = random.Random(seed)
    img = Image.new("RGB", (W, H), (190, 190, 185))
    _gradient(img, (205, 205, 200), (175, 175, 170), 0, 640)
    _gradient(img, (120, 118, 112), (90, 88, 84), 640, H)
    d = ImageDraw.Draw(img)
    # wall stripe + sign
    d.rectangle([0, 560, W, 640], fill=(220, 180, 40))
    for x in range(0, W, 80):
        d.polygon([(x, 560), (x + 40, 560), (x + 80, 640), (x + 40, 640)], fill=(40, 40, 40))
    # lamps
    for x in (300, 700, 1100):
        d.rectangle([x - 90, 0, x + 90, 26], fill=(250, 250, 240))
        d.polygon([(x - 90, 26), (x + 90, 26), (x + 220, 560), (x - 220, 560)], fill=(214, 214, 208))
    _sign(d, (540, 70, 860, 140), "SERVICE BAY 2", (240, 240, 240), (40, 40, 40), size=36)
    # tool cabinet
    d.rectangle([60, 420, 300, 760], fill=(190, 40, 40), outline=(120, 20, 20), width=4)
    for i in range(6):
        d.rectangle([75, 440 + i * 52, 285, 480 + i * 52], fill=(210, 60, 60), outline=(120, 20, 20), width=2)
        d.rectangle([160, 455 + i * 52, 200, 465 + i * 52], fill=(230, 230, 230))
    # lift + car
    draw_lift(d, 460, 560, 560)
    draw_car(d, 460, 560, 560, (235, 235, 235))
    # oil drain + jack
    d.rectangle([760, 760, 860, 860], fill=(60, 60, 60))
    d.ellipse([740, 740, 880, 780], fill=(80, 80, 80))
    d.polygon([(1150, 860), (1290, 860), (1270, 800), (1170, 800)], fill=(200, 60, 40))
    d.rectangle([1200, 760, 1240, 800], fill=(60, 60, 60))
    # tyres
    for i, (tx, ty) in enumerate([(1180, 500), (1250, 500), (1215, 440)]):
        d.ellipse([tx, ty, tx + 80, ty + 80], fill=(30, 30, 30))
        d.ellipse([tx + 25, ty + 25, tx + 55, ty + 55], fill=(150, 150, 150))
    # floor markings
    d.rectangle([380, 900, 1120, 912], fill=(230, 200, 60))
    img = _finish(img, seed)
    img = watermark(img)
    save_jpg(img, out)
