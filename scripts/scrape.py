"""Scrape vendors for one compound from the command line (useful when tuning a scraper).

    python -m scripts.scrape "Topiramate"
    python -m scripts.scrape 97240-79-4 --vendor medchemexpress
"""

from __future__ import annotations

import argparse

from core import resolver
from core.db import init_db
from core.pricing import scrape_compound
from scrapers.registry import enabled_scrapers, get_scraper


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", help="name, CAS or SMILES")
    p.add_argument("--vendor", action="append", help="vendor key (repeatable); default = ENABLED_VENDORS")
    args = p.parse_args()

    init_db()
    res = resolver.resolve(args.query)
    if not res.compound:
        print(res.error or f"Ambiguous: {[c.label for c in res.candidates]}")
        return
    c = res.compound
    print(f"Compound: {c.label}  CAS={c.cas}  InChIKey={c.inchikey}")
    scrapers = [get_scraper(k) for k in args.vendor] if args.vendor else enabled_scrapers()
    offers, warnings = scrape_compound(c, scrapers)
    for o in offers:
        price = "quote only" if o.quote_only else f"{o.price} {o.currency} (A${o.price_aud_per_g}/g)"
        print(f"  {o.vendor:<18} {o.pack_qty} {o.pack_unit:<4} {price}  purity={o.purity}")
    for w in warnings:
        print("  !", w)


if __name__ == "__main__":
    main()
