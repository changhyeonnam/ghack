"""PDF text-layer cross-check.

Most mobile-banking statements are born-digital PDFs with a text layer. We never *trust* the text layer for
extraction (layouts vary too much), but it is a free, exact oracle to verify what the model read:
  * does every extracted amount/date actually occur as text on the page it was attributed to?
  * does the bounding box the model returned overlap the words carrying that amount?
The result is attached to the extraction and feeds the Challenger (Q9: every number sourced).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import pymupdf

from ..schemas import BankStatementExtraction, SourceRef

AMOUNT_CHARS = re.compile(r"[^\d]")


@dataclass
class PageWords:
    width: float
    height: float
    words: list[tuple[float, float, float, float, str]]  # x0, y0, x1, y1, text
    digits_index: dict[str, list[tuple[float, float, float, float]]] = field(default_factory=dict)


def _digits(s: str) -> str:
    return AMOUNT_CHARS.sub("", s)


def load_pages(pdf_bytes: bytes) -> list[PageWords]:
    pages: list[PageWords] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            words = [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]
            pw = PageWords(width=page.rect.width, height=page.rect.height, words=words)
            for x0, y0, x1, y1, t in words:
                d = _digits(t)
                if len(d) >= 3:
                    pw.digits_index.setdefault(d, []).append((x0, y0, x1, y1))
            pages.append(pw)
    return pages


def has_text_layer(pages: list[PageWords]) -> bool:
    return sum(len(p.words) for p in pages) >= 20


def _amount_variants(value: float) -> set[str]:
    i = int(round(value))
    out = {str(i)}
    if abs(value - i) > 1e-6:
        out.add(str(int(round(value * 100))))      # 14800.50 -> "1480050" (printed as 14,800.50)
    out.add(str(i) + "00")                          # 14800 printed as 14,800.00
    return out


def _bbox_overlaps(ref: SourceRef, box: tuple[float, float, float, float], pw: PageWords, slack: float = 0.02) -> bool:
    if not ref.bbox:
        return False
    x0, y0, x1, y1 = box
    cy = (y0 + y1) / 2 / pw.height
    cx = (x0 + x1) / 2 / pw.width
    return (ref.bbox.ymin / 1000 - slack) <= cy <= (ref.bbox.ymax / 1000 + slack) and (ref.bbox.xmin / 1000 - slack) <= cx <= (ref.bbox.xmax / 1000 + slack)


@dataclass
class CrossCheck:
    text_layer: bool
    rows: int = 0
    amounts_found: int = 0
    amounts_missing: list[dict] = field(default_factory=list)   # {row_id, date, amount, page}
    bbox_hits: int = 0
    bbox_misses: list[str] = field(default_factory=list)       # row ids whose bbox does not cover the amount text
    dates_found: int = 0

    @property
    def amount_match_rate(self) -> Optional[float]:
        return round(self.amounts_found / self.rows, 4) if self.rows else None

    @property
    def bbox_match_rate(self) -> Optional[float]:
        return round(self.bbox_hits / self.amounts_found, 4) if self.amounts_found else None

    def to_dict(self) -> dict:
        return {"text_layer": self.text_layer, "rows": self.rows, "amounts_found": self.amounts_found, "amount_match_rate": self.amount_match_rate,
                "amounts_missing": self.amounts_missing[:50], "bbox_hits": self.bbox_hits, "bbox_match_rate": self.bbox_match_rate,
                "bbox_misses": self.bbox_misses[:50], "dates_found": self.dates_found}


def cross_check_statement(pdf_bytes: bytes, ex: BankStatementExtraction) -> CrossCheck:
    pages = load_pages(pdf_bytes)
    cc = CrossCheck(text_layer=has_text_layer(pages))
    if not cc.text_layer:
        return cc
    for t in ex.transactions:
        cc.rows += 1
        amount = t.credit if t.credit > 0 else t.debit
        p = t.source.page
        pw = pages[p - 1] if 1 <= p <= len(pages) else None
        found_boxes: list[tuple[float, float, float, float]] = []
        if pw and amount > 0:
            for v in _amount_variants(amount):
                found_boxes += pw.digits_index.get(v, [])
        if found_boxes:
            cc.amounts_found += 1
            if any(_bbox_overlaps(t.source, b, pw) for b in found_boxes):
                cc.bbox_hits += 1
            else:
                cc.bbox_misses.append(t.row_id)
        else:
            cc.amounts_missing.append({"row_id": t.row_id, "date": t.date, "amount": amount, "page": p})
        # date: look for the day/month digits of the ISO date on the page (dd/mm or mm/dd forms)
        if pw and len(t.date) >= 10:
            y, m, d = t.date[:4], t.date[5:7], t.date[8:10]
            if any(k in pw.digits_index for k in (d + m + y, m + d + y, y + m + d, d + m + y[2:], m + d + y[2:])):
                cc.dates_found += 1
    return cc
