"""Static sector reference bands used to sanity-check scale. Illustrative, not a credit model."""
from __future__ import annotations

BENCHMARKS: dict[tuple[str, str], dict] = {
    ("grocery retail", "ID"): {"monthly_revenue_band": (15_000_000, 60_000_000), "currency": "IDR", "gross_margin": (0.08, 0.18),
                               "seasonality": "Spikes before Ramadan/Eid and year-end; otherwise flat.", "cash_share": "High: 40-70% cash, rest QRIS/transfer."},
    ("apparel e-commerce", "VN"): {"monthly_revenue_band": (30_000_000, 200_000_000), "currency": "VND", "gross_margin": (0.25, 0.45),
                                   "seasonality": "Peaks on 11.11, 12.12 and before Tet; dip in Feb-Mar.", "cash_share": "Low: platform payouts dominate, COD deposited in lumps."},
    ("auto repair", "PH"): {"monthly_revenue_band": (60_000, 250_000), "currency": "PHP", "gross_margin": (0.30, 0.50),
                            "seasonality": "Mild; rainy season (Jun-Sep) brings more repair jobs.", "cash_share": "Very high: mostly cash and GCash, weekly deposits typical."},
}
DEFAULT = {"monthly_revenue_band": None, "currency": None, "gross_margin": None,
           "seasonality": "No sector-specific seasonality reference available.", "cash_share": "Unknown."}


def lookup_sector_benchmark(sector: str, country: str) -> dict:
    """Return typical revenue band, margin and seasonality notes for a sector/country pair."""
    key = (sector.strip().lower(), country.strip().upper())
    for (s, c), v in BENCHMARKS.items():
        if c == key[1] and (s == key[0] or any(tok in key[0] for tok in s.split())):
            return {"sector": s, "country": c, **v}
    return {"sector": sector, "country": country, **DEFAULT}
