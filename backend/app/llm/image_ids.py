"""Stable identities for rendered page images, used in LLM cache keys.

PDF pages are rasterised by PyMuPDF, and the JPEG bytes differ between macOS and the linux container, so a cache key
built from image bytes misses on Cloud Run for runs cached on a laptop. Every renderer registers its output here as
"<source document sha256>:<view>"; the cache key uses that identity instead of the bytes when it is known.
"""
from __future__ import annotations

import hashlib

_IDS: dict[str, str] = {}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def register(data: bytes, identity: str) -> None:
    _IDS[_digest(data)] = identity


def identity_of(data: bytes) -> str | None:
    return _IDS.get(_digest(data))
