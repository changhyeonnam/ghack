"""Document utilities: type probing, page rendering, perceptual hashing.

Everything the LLM sees is a *page image*. We render PDFs ourselves (PyMuPDF) so the coordinates Gemini
returns (normalized 0-1000 per image) map 1:1 onto what the UI displays.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import pymupdf as fitz
import imagehash
from PIL import Image, ImageOps

IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
PDF_MIME = "application/pdf"


def sniff_mime(filename: str, data: bytes) -> str:
    head = data[:12]
    if head.startswith(b"%PDF"):
        return PDF_MIME
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return PDF_MIME
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def page_count(data: bytes, mime: str) -> int:
    if mime == PDF_MIME:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return doc.page_count
    return 1


def _open_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def render_page(data: bytes, mime: str, page: int, dpi: int = 110, max_width: int | None = None) -> bytes:
    """Return PNG bytes for a 1-based page."""
    if mime == PDF_MIME:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if page < 1 or page > doc.page_count:
                raise IndexError(f"page {page} out of range 1..{doc.page_count}")
            pix = doc[page - 1].get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        if page != 1:
            raise IndexError("images have a single page")
        img = _open_image(data)
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@dataclass
class LlmPage:
    page: int
    mime_type: str
    data: bytes
    width: int
    height: int


def pages_for_llm(data: bytes, mime: str, max_width: int = 1200, dpi: int = 130) -> list[LlmPage]:
    """JPEG renders sized for the model: enough resolution to read small print, few enough tokens to be cheap."""
    out: list[LlmPage] = []
    n = page_count(data, mime)
    for p in range(1, n + 1):
        png = render_page(data, mime, p, dpi=dpi, max_width=max_width)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        out.append(LlmPage(page=p, mime_type="image/jpeg", data=buf.getvalue(), width=img.width, height=img.height))
    return out


def thumbnail(data: bytes, mime: str, max_width: int = 480) -> bytes:
    png = render_page(data, mime, 1, dpi=60, max_width=max_width)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


def phash_pages(data: bytes, mime: str) -> list[str]:
    """Perceptual hash per page (hex). Near-identical images differ by a small Hamming distance."""
    hashes: list[str] = []
    for p in range(1, page_count(data, mime) + 1):
        png = render_page(data, mime, p, dpi=72, max_width=800)
        img = Image.open(io.BytesIO(png)).convert("L")
        hashes.append(str(imagehash.phash(img, hash_size=16)))
    return hashes


def phash_distance(a: str, b: str) -> int:
    """Hamming distance between two hex hashes; incomparable sizes count as 'different'."""
    if not a or not b or len(a) != len(b):
        return 999
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def phash16_of_file(path: str) -> str:
    with Image.open(path) as im:
        return str(imagehash.phash(im.convert("L"), hash_size=16))
