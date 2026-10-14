"""Shared constants, case profiles and rendering helpers for the LedgerLens synthetic dataset.

Everything here is fictional. No real customer, merchant or bank data is used.
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SYNTH_DIR = Path(__file__).resolve().parent
WATERMARK = "SYNTHETIC · FOR DEMO"

# --------------------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------------------
FONT_DIRS = [Path("/System/Library/Fonts/Supplemental"), Path("/System/Library/Fonts")]
FONT_FILES = {
    "sans": "Arial.ttf",
    "sans_bold": "Arial Bold.ttf",
    "sans_black": "Arial Black.ttf",
    "mono": "Courier New.ttf",
    "mono_bold": "Courier New Bold.ttf",
    "mono2": "Andale Mono.ttf",
    "hand": "Bradley Hand Bold.ttf",
    "hand2": "Noteworthy.ttc",
    "hand3": "Chalkboard.ttc",
    "marker": "MarkerFelt.ttc",
    "unicode": "Arial Unicode.ttf",
    "helv": "Helvetica.ttc",
}
_font_cache: dict = {}


def font(kind: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    """Load a TrueType font by nickname with graceful fallback to Arial / PIL default."""
    key = (kind, size, index)
    if key in _font_cache:
        return _font_cache[key]
    f = None
    name = FONT_FILES.get(kind, kind)
    for d in FONT_DIRS:
        p = d / name
        if p.exists():
            try:
                f = ImageFont.truetype(str(p), size, index=index)
                break
            except Exception:  # pragma: no cover - font loading edge cases
                f = None
    if f is None:
        for d in FONT_DIRS:
            p = d / "Arial.ttf"
            if p.exists():
                try:
                    f = ImageFont.truetype(str(p), size)
                    break
                except Exception:
                    f = None
    if f is None:
        f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def font_path(kind: str) -> str | None:
    name = FONT_FILES.get(kind, kind)
    for d in FONT_DIRS:
        p = d / name
        if p.exists():
            return str(p)
    return None


# --------------------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------------------
def fmt_amount(v, currency: str) -> str:
    """Local number formatting: IDR/VND with dot thousands, PHP with comma thousands + 2 dp."""
    if currency in ("IDR", "VND"):
        return f"{int(round(v)):,}".replace(",", ".")
    if currency == "PHP":
        return f"{float(v):,.2f}"
    return f"{v:,}"


def fmt_date_local(d: date, country: str) -> str:
    if country == "PH":
        return d.strftime("%m/%d/%Y")
    return d.strftime("%d/%m/%Y")


def iso(d: date) -> str:
    return d.isoformat()


def month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1))
    return start, end


def days_in_month(year: int, month: int):
    s, e = month_range(year, month)
    d = s
    while d <= e:
        yield d
        d += timedelta(days=1)


def round_to(v: float, step: int) -> int:
    return int(round(v / step) * step)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def norm_bbox(x0: float, y0: float, x1: float, y1: float, w: float, h: float) -> list[int]:
    """Return [ymin, xmin, ymax, xmax] normalized to 0-1000 (top-left origin coordinates in)."""
    return [
        int(round(1000 * y0 / h)),
        int(round(1000 * x0 / w)),
        int(round(1000 * y1 / h)),
        int(round(1000 * x1 / w)),
    ]


# --------------------------------------------------------------------------------------
# Image helpers
# --------------------------------------------------------------------------------------
def text_size(draw: ImageDraw.ImageDraw, text: str, f) -> tuple[int, int]:
    b = draw.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]


def watermark(img: Image.Image, scale: float = 1.0, corner: str = "br") -> Image.Image:
    """Stamp the SYNTHETIC watermark into the bottom-right corner of a PIL image."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font("sans_bold", max(14, int(22 * scale)))
    w, h = text_size(d, WATERMARK, f)
    pad = int(10 * scale)
    x = img.width - w - int(18 * scale)
    y = img.height - h - int(18 * scale)
    d.rectangle([x - pad, y - pad, x + w + pad, y + h + pad], fill=(255, 255, 255, 185))
    d.text((x, y), WATERMARK, font=f, fill=(110, 110, 110, 255))
    out = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return out


def photo_effect(
    flat: Image.Image,
    seed: int,
    angle: float | None = None,
    bg=(40, 38, 42),
    pad: int = 55,
    noise: float = 5.0,
    vignette: float = 0.25,
):
    """Make a flat document render look like a phone photo: rotation, shadow, lighting, noise.

    Fully deterministic for a given seed so two renders that differ only in a few glyphs
    produce images that differ only in those glyphs (used by the duplicate-document traps).
    Returns (image, map_box) where map_box([x0, y0, x1, y1]) maps a rectangle in flat-image
    pixel coordinates to the enclosing rectangle in the output image.
    """
    import math

    r = random.Random(seed)
    rng = np.random.default_rng(seed)
    if angle is None:
        angle = r.uniform(-3.0, 3.0)
    fw, fh = flat.size
    rgba = flat.convert("RGBA").rotate(angle, resample=Image.BICUBIC, expand=True)
    rw, rh = rgba.size
    W, H = rw + 2 * pad, rh + 2 * pad
    canvas = Image.new("RGBA", (W, H), bg + (255,))
    # soft shadow under the paper
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 150), (0, 0, rgba.width, rgba.height), mask=rgba.split()[3])
    shadow.paste(sh, (pad + 8, pad + 10), sh)
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.paste(rgba, (pad, pad), rgba)
    arr = np.asarray(canvas.convert("RGB")).astype(np.float32)
    # lighting gradient (one side a little brighter)
    yy, xx = np.mgrid[0:H, 0:W]
    gx = (xx / W - 0.5) * r.uniform(-1, 1)
    gy = (yy / H - 0.5) * r.uniform(-1, 1)
    light = 1.0 + 0.10 * (gx + gy)
    # vignette
    cx, cy = W / 2, H / 2
    dist = np.sqrt(((xx - cx) / W) ** 2 + ((yy - cy) / H) ** 2) * 2
    vig = 1.0 - vignette * np.clip(dist - 0.55, 0, 1)
    arr *= (light * vig)[..., None]
    arr += rng.normal(0, noise, arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

    th = math.radians(angle)
    cos_t, sin_t = math.cos(th), math.sin(th)

    def map_point(x, y):
        dx, dy = x - fw / 2, y - fh / 2
        # PIL rotates counter-clockwise (visually) in y-down image coordinates
        nx = dx * cos_t + dy * sin_t + rw / 2 + pad
        ny = -dx * sin_t + dy * cos_t + rh / 2 + pad
        return nx, ny

    def map_box(box):
        x0, y0, x1, y1 = box
        pts = [map_point(x0, y0), map_point(x1, y0), map_point(x0, y1), map_point(x1, y1)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return [max(0, min(xs)), max(0, min(ys)), min(W, max(xs)), min(H, max(ys))]

    return out, map_box


def paper_texture(img: Image.Image, seed: int, strength: float = 4.0) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    arr += rng.normal(0, strength, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def save_jpg(img: Image.Image, path: Path, quality: int = 85) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=quality, optimize=True)


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "PNG", optimize=True)


# --------------------------------------------------------------------------------------
# Case profiles
# --------------------------------------------------------------------------------------
CASES = {
    "A": {
        "case_id": "A",
        "name": "Warung Ibu Sari",
        "business_name": "Warung Ibu Sari",
        "sector": "grocery retail",
        "country": "ID",
        "city": "Jakarta",
        "language": "id",
        "currency": "IDR",
        "requested_amount": 25_000_000,
        "expected_outcome": "approve",
        "account_holder": "SARI DEWI",
        "bank_name": "Bank Nusantara Digital (synthetic)",
        "bank_short": "Nusantara Digital",
        "account_masked": "1120 **** **** 7781",
        "statement_filename": "bank_statement_2026H1.pdf",
        "period": ("2026-01-01", "2026-06-30"),
    },
    "B": {
        "case_id": "B",
        "name": "Linh Fashion Online",
        "business_name": "Linh Fashion Official",
        "sector": "online apparel retail (Shopee seller)",
        "country": "VN",
        "city": "Ho Chi Minh City",
        "language": "vi",
        "currency": "VND",
        "requested_amount": 150_000_000,
        "expected_outcome": "approve_with_conditions",
        "account_holder": "NGUYEN THI LINH",
        "bank_name": "Ngan Hang So Saigon Mekong (synthetic)",
        "bank_short": "SaigonMekong Digital",
        "account_masked": "0071 **** **** 3392",
        "statement_filename": "bank_statement_2025-12_2026-05.pdf",
        "period": ("2025-12-01", "2026-05-31"),
    },
    "C": {
        "case_id": "C",
        "name": "Reyes Auto Repair",
        "business_name": "Reyes Auto Repair",
        "sector": "motor vehicle repair",
        "country": "PH",
        "city": "Manila",
        "language": "tl+en",
        "currency": "PHP",
        "requested_amount": 250_000,
        "expected_outcome": "request_more_documents",
        "account_holder": "RAMON REYES",
        "bank_name": "Metro Pacific Savings Bank (synthetic)",
        "bank_short": "MetroPacific Savings",
        "account_masked": "0045-****-**-6610",
        "statement_filename": "bank_statement_2026_partial.pdf",
        "period": ("2026-01-01", "2026-06-30"),
    },
}

FIL_MONTHS = {1: "Enero", 2: "Pebrero", 3: "Marso", 4: "Abril", 5: "Mayo", 6: "Hunyo"}
EN_MONTHS = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 12: "December"}
