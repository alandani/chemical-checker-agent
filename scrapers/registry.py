"""Map vendor keys to scraper instances.

To add a custom scraper for a vendor, subclass GenericSearchScraper (or VendorScraper)
in scrapers/<vendor>.py and register it in CUSTOM below.
"""

from __future__ import annotations

from core.config import get_settings
from scrapers.base import VendorScraper
from scrapers.generic import GenericSearchScraper
from scrapers.vendors import VENDORS, VENDORS_BY_KEY

CUSTOM: dict[str, type[VendorScraper]] = {
    # "sigma": SigmaScraper,
}


def get_scraper(key: str) -> VendorScraper:
    info = VENDORS_BY_KEY[key]
    cls = CUSTOM.get(key, GenericSearchScraper)
    return cls(info)


def enabled_scrapers(regions: list[str] | None = None) -> list[VendorScraper]:
    keys = get_settings().enabled_vendor_keys
    scrapers = [get_scraper(k) for k in keys if k in VENDORS_BY_KEY]
    if regions:
        wanted = [r.lower() for r in regions]
        scrapers = [s for s in scrapers if any(w in s.info.region.lower() for w in wanted)]
    return scrapers


def all_regions() -> list[str]:
    return sorted({v.region for v in VENDORS})
