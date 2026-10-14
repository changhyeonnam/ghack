"""USD per 1M tokens, from ai.google.dev/gemini-api/docs/pricing (checked 2026-10-14).

Used only for the per-case cost figure shown in the UI and the benchmark. Unknown models fall back to Flash.
"""
from __future__ import annotations

PRICES: dict[str, tuple[float, float]] = {
    # model: (input, output). Thinking tokens are billed as output.
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.1-pro-preview": (2.00, 12.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-4-argon": (2.00, 10.00),
}
DEFAULT = (0.75, 3.75)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int, thinking_tokens: int = 0) -> float:
    key = model.split("/")[-1]
    p_in, p_out = PRICES.get(key, DEFAULT)
    return round((input_tokens * p_in + (output_tokens + thinking_tokens) * p_out) / 1_000_000, 6)
