"""Load known reactions (e.g. a USPTO subset) into the reactions table.

Accepts a CSV with either:
  * a reaction SMILES column (default name: rxn_smiles), format "A.B>reagents>P" or "A.B>>P"
    (atom maps are stripped), or
  * separate `reactants` and `product` columns (reactants dot-separated).
Optional columns: yield (0-1 or percent), conditions, reference.

    python -m scripts.load_reactions data/uspto_50k.csv --limit 50000
"""

from __future__ import annotations

import argparse
import csv

from core import chem, repository
from core.db import init_db
from core.models import RouteStep


def parse_yield(value: str | None) -> float | None:
    if not value:
        return None
    try:
        y = float(str(value).strip().rstrip("%"))
    except ValueError:
        return None
    return y / 100 if y > 1 else y


def rows_to_steps(rows, rxn_col: str):
    for row in rows:
        if row.get(rxn_col):
            parts = row[rxn_col].split(">")
            if len(parts) != 3:
                continue
            reactants_raw, reagents, product_raw = parts
        else:
            reactants_raw, reagents, product_raw = row.get("reactants", ""), "", row.get("product", "")
        reactants = [chem.strip_atom_maps(s) for s in reactants_raw.split(".") if s]
        products = [chem.strip_atom_maps(s) for s in product_raw.split(".") if s]
        if not reactants or not products:
            continue
        product = max(products, key=len)  # main product
        conditions = row.get("conditions") or (reagents.replace(".", ", ") if reagents else None)
        yield RouteStep(
            reactants=reactants,
            product=product,
            conditions=conditions or None,
            yield_=parse_yield(row.get("yield")),
            reference=row.get("reference") or row.get("id") or None,
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_path")
    p.add_argument("--rxn-col", default="rxn_smiles")
    p.add_argument("--source", default="uspto")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    init_db()
    loaded = skipped = 0
    with open(args.csv_path, newline="") as f:
        for step in rows_to_steps(csv.DictReader(f), args.rxn_col):
            ik = chem.inchikey(step.product)
            if not ik:
                skipped += 1
                continue
            repository.add_reaction(step, ik, source=args.source)
            loaded += 1
            if args.limit and loaded >= args.limit:
                break
            if loaded % 5000 == 0:
                print(f"  {loaded} reactions…")
    print(f"Loaded {loaded} reactions ({skipped} skipped).")


if __name__ == "__main__":
    main()
