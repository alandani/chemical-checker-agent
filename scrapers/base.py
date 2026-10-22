"""Scraper interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.models import Compound


class ScrapeError(Exception):
    pass


@dataclass
class RawOffer:
    """An offer as the vendor shows it, before unit/currency normalisation."""

    pack: str | None = None  # e.g. "5g", "100 mg"
    pack_qty: float | None = None
    pack_unit: str | None = None
    price: float | None = None
    currency: str | None = None
    purity: float | None = None  # percent
    url: str | None = None
    in_stock: bool | None = None
    quote_only: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class VendorInfo:
    key: str
    name: str
    region: str
    base_url: str
    # Search URL with {q} placeholder (CAS preferred, else name). Verify against the live site.
    search_url: str | None = None
    # Optional URL used when the compound has no CAS number (falls back to search_url).
    name_search_url: str | None = None
    requires_js: bool = False
    verified: bool = False  # set True once the search URL + extraction is tested live
    notes: str = ""


class VendorScraper(ABC):
    info: VendorInfo

    def __init__(self, info: VendorInfo):
        self.info = info

    @property
    def key(self) -> str:
        return self.info.key

    @property
    def name(self) -> str:
        return self.info.name

    @abstractmethod
    def search(self, compound: Compound) -> list[RawOffer]:
        """Return offers for exactly this compound. Raise ScrapeError on failure."""
