"""Pricing: find offers for a compound and work out the cheapest way to buy an amount.

Lookup order: fresh offers in the database -> on-demand scrape of enabled vendors
(in parallel, with a per-vendor timeout) -> store results.
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from core import fx, repository
from core.config import get_settings
from core.models import Compound, Offer, Purchase
from core.units import parse_pack, to_grams
from scrapers.base import RawOffer, ScrapeError, VendorScraper

log = logging.getLogger(__name__)


def normalise(raw: RawOffer, vendor: str, inchikey: str) -> Offer:
    qty, unit = raw.pack_qty, raw.pack_unit
    if (qty is None or unit is None) and raw.pack:
        parsed = parse_pack(raw.pack)
        if parsed:
            qty, unit = parsed
    grams = to_grams(qty, unit)
    price_aud = None if raw.quote_only else fx.to_base(raw.price, raw.currency)
    per_g = price_aud / grams if price_aud is not None and grams else None
    return Offer(
        vendor=vendor,
        compound_inchikey=inchikey,
        pack_qty=qty,
        pack_unit=unit,
        pack_grams=grams,
        price=raw.price,
        currency=(raw.currency or "").upper() or None,
        price_aud=round(price_aud, 2) if price_aud is not None else None,
        price_aud_per_g=round(per_g, 4) if per_g is not None else None,
        purity=raw.purity,
        url=raw.url,
        in_stock=raw.in_stock,
        quote_only=raw.quote_only or raw.price is None,
    )


def _scrape_one(scraper: VendorScraper, compound: Compound) -> tuple[str, list[Offer] | None, str | None]:
    try:
        raws = scraper.search(compound)
        offers = [normalise(r, scraper.name, compound.inchikey) for r in raws]
        return scraper.key, offers, None
    except ScrapeError as exc:
        return scraper.key, None, str(exc)
    except Exception as exc:  # never let one vendor break the run
        log.exception("Scraper %s crashed", scraper.key)
        return scraper.key, None, f"{scraper.name}: unexpected error: {exc}"


def scrape_compound(compound: Compound, scrapers: list[VendorScraper]) -> tuple[list[Offer], list[str]]:
    """Scrape vendors in parallel. Returns (offers, warnings)."""
    from scrapers.vendors import VENDORS_BY_KEY

    settings = get_settings()
    warnings: list[str] = []
    found: list[Offer] = []
    if not scrapers:
        return found, warnings
    for s in scrapers:
        repository.upsert_vendor(s.key, s.info.name, s.info.region, s.info.base_url)

    pool = ThreadPoolExecutor(max_workers=min(8, len(scrapers)))
    futures = {pool.submit(_scrape_one, s, compound): s for s in scrapers}
    try:
        for fut, scraper in futures.items():
            try:
                key, offers, error = fut.result(timeout=settings.scrape_timeout_s + 5)
            except FutureTimeout:
                key, offers, error = scraper.key, None, f"{scraper.name}: timed out"
            repository.record_scrape(key, ok=offers is not None, error=error)
            if offers is None:
                warnings.append(error or f"{scraper.name}: failed")
                continue
            repository.replace_offers(compound.inchikey, VENDORS_BY_KEY[key].name, offers)
            found.extend(offers)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return found, warnings


def get_offers(
    compound: Compound,
    regions: list[str] | None = None,
    force_refresh: bool = False,
) -> tuple[list[Offer], list[str]]:
    """Return (offers, warnings) for a compound, scraping on demand if the cache is stale."""
    from scrapers.registry import enabled_scrapers

    settings = get_settings()
    cached = repository.get_offers(compound.inchikey, max_age_days=settings.offer_max_age_days)
    real_cached = [o for o in cached if not o.is_demo]
    # Sample offers never stand in for a live search: only fresh real offers skip scraping.
    if (real_cached or (cached and not settings.enable_live_scraping)) and not force_refresh:
        return cached, []
    if not settings.enable_live_scraping:
        return cached, ([] if cached else ["Live scraping is disabled (ENABLE_LIVE_SCRAPING=false)."])

    scraped, warnings = scrape_compound(compound, enabled_scrapers(regions))
    demo = [o for o in cached if o.is_demo]
    return scraped + demo, warnings


def meets_purity(offer: Offer, min_purity: float | None) -> bool:
    if min_purity is None:
        return True
    return offer.purity is None or offer.purity >= min_purity  # unknown purity is shown, not excluded


def cheapest_purchase(offers: list[Offer], grams: float, min_purity: float | None = None) -> Purchase | None:
    """Cheapest single-offer purchase covering `grams`, buying whole packs."""
    best: Purchase | None = None
    for o in offers:
        if o.quote_only or o.price_aud is None or not o.pack_grams or not meets_purity(o, min_purity):
            continue
        n = max(1, math.ceil(grams / o.pack_grams - 1e-9))
        total = n * o.price_aud
        if best is None or total < best.total_aud:
            best = Purchase(offer=o, n_packs=n, total_aud=round(total, 2))
    return best
