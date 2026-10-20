"""Pack-size parsing and unit conversion."""

from __future__ import annotations

import re

_MASS_TO_G = {
    "ug": 1e-6,
    "µg": 1e-6,
    "mcg": 1e-6,
    "mg": 1e-3,
    "g": 1.0,
    "gm": 1.0,
    "kg": 1e3,
}
_VOLUME_TO_ML = {"ul": 1e-3, "µl": 1e-3, "ml": 1.0, "l": 1e3}

_PACK_RE = re.compile(r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>[a-zA-Zµ]+)")


def parse_pack(text: str) -> tuple[float, str] | None:
    """Parse strings like '5g', '100 mg', '1 KG', '25mL' into (qty, unit)."""
    m = _PACK_RE.search(text or "")
    if not m:
        return None
    qty = float(m.group("qty").replace(",", "."))
    unit = m.group("unit").lower()
    if unit in _MASS_TO_G or unit in _VOLUME_TO_ML:
        return qty, unit
    return None


def to_grams(qty: float | None, unit: str | None, density_g_per_ml: float | None = None) -> float | None:
    """Convert a pack size to grams. Volumes need a density, otherwise None."""
    if qty is None or unit is None:
        return None
    u = unit.lower().strip()
    if u in _MASS_TO_G:
        return qty * _MASS_TO_G[u]
    if u in _VOLUME_TO_ML and density_g_per_ml:
        return qty * _VOLUME_TO_ML[u] * density_g_per_ml
    return None
