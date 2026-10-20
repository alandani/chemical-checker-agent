"""Currency conversion to the base currency (AUD by default).

Live rates come from the free Frankfurter API (ECB reference rates). If the
API is unreachable, approximate fallback rates are used and flagged.
"""

from __future__ import annotations

import time

import httpx

from core.config import get_settings

# Approximate fallback rates to AUD. Only used when the live API is unreachable.
FALLBACK_TO_AUD = {
    "AUD": 1.0,
    "USD": 1.52,
    "EUR": 1.65,
    "GBP": 1.95,
    "CHF": 1.75,
    "CNY": 0.21,
    "JPY": 0.0101,
    "INR": 0.018,
}

_cache: dict[str, tuple[float, float, bool]] = {}  # currency -> (rate, fetched_at, is_fallback)
_TTL_S = 6 * 3600


def rate_to_base(currency: str) -> tuple[float | None, bool]:
    """Return (rate, is_fallback) to convert 1 unit of `currency` into the base currency."""
    settings = get_settings()
    cur = currency.upper().strip()
    base = settings.base_currency.upper()
    if cur == base:
        return 1.0, False

    cached = _cache.get(cur)
    if cached and time.time() - cached[1] < _TTL_S:
        return cached[0], cached[2]

    try:
        r = httpx.get(
            "https://api.frankfurter.app/latest",
            params={"from": cur, "to": base},
            timeout=settings.http_timeout_s,
        )
        r.raise_for_status()
        rate = float(r.json()["rates"][base])
        _cache[cur] = (rate, time.time(), False)
        return rate, False
    except Exception:
        if base == "AUD" and cur in FALLBACK_TO_AUD:
            rate = FALLBACK_TO_AUD[cur]
            _cache[cur] = (rate, time.time(), True)
            return rate, True
        return None, True


def to_base(amount: float | None, currency: str | None) -> float | None:
    if amount is None or not currency:
        return None
    rate, _ = rate_to_base(currency)
    return amount * rate if rate is not None else None


def cached_rates() -> dict[str, dict]:
    """For the Data admin page."""
    return {
        cur: {"rate": rate, "fetched_at": fetched, "fallback": fb}
        for cur, (rate, fetched, fb) in _cache.items()
    }
