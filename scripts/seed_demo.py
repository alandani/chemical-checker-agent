"""Create the database tables, register vendors and load the offline demo data.

    python -m scripts.seed_demo            # tables + vendors + demo data
    python -m scripts.seed_demo --no-demo  # tables + vendors only
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import delete

from core import chem, repository
from core.config import DATA_DIR
from core.db import OfferRow, ReactionRow, init_db, session_scope
from core.models import Compound, RouteStep
from core.pricing import normalise
from scrapers.base import RawOffer
from scrapers.vendors import VENDORS

DEMO_FILE = DATA_DIR / "demo" / "demo_data.json"


def register_vendors() -> None:
    for v in VENDORS:
        repository.upsert_vendor(v.key, v.name, v.region, v.base_url)


def load_demo() -> dict[str, int]:
    data = json.loads(DEMO_FILE.read_text())
    by_cas: dict[str, Compound] = {}
    for c in data["compounds"]:
        info = chem.describe(c["smiles"])
        if info is None:
            raise ValueError(f"Bad SMILES in demo data: {c['smiles']}")
        compound = Compound(name=c["name"], cas=c["cas"], **info)
        repository.upsert_compound(compound, synonyms=c.get("synonyms"))
        by_cas[c["cas"]] = compound

    with session_scope() as s:  # idempotent: clear previous demo rows
        s.execute(delete(OfferRow).where(OfferRow.is_demo.is_(True)))
        s.execute(delete(ReactionRow).where(ReactionRow.source == "demo"))

    offers = []
    for o in data["offers"]:
        compound = by_cas[o["cas"]]
        offer = normalise(
            RawOffer(
                pack=o["pack"],
                price=o.get("price"),
                currency=o.get("currency"),
                purity=o.get("purity"),
                in_stock=o.get("in_stock"),
                quote_only=o.get("quote_only", False),
            ),
            vendor=o["vendor"],
            inchikey=compound.inchikey,
        )
        offer.is_demo = True
        offers.append(offer)
    repository.add_offers(offers)

    for r in data["reactions"]:
        product = by_cas[r["product_cas"]]
        step = RouteStep(
            reactants=[by_cas[c].smiles for c in r["reactants_cas"]],
            product=product.smiles,
            equivalents=r.get("equivalents"),
            conditions=r.get("conditions"),
            yield_=r.get("yield"),
            reference=r.get("reference"),
        )
        repository.add_reaction(step, product.inchikey, source="demo")

    return {"compounds": len(by_cas), "offers": len(offers), "reactions": len(data["reactions"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-demo", action="store_true", help="skip the sample data")
    args = parser.parse_args()
    init_db()
    register_vendors()
    print(f"Registered {len(VENDORS)} vendors.")
    if not args.no_demo:
        counts = load_demo()
        print("Loaded demo data:", counts)


if __name__ == "__main__":
    main()
