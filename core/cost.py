"""Cost model.

make cost = Σ (grams of each starting material needed, allowing for each step's yield)
            × cheapest pack price, then × (1 + consumables margin) for solvents/workup.
"""

from __future__ import annotations

from collections import defaultdict

from core import chem, fx
from core.models import CostBreakdown, MaterialCost, Purchase, Query, Route, RouteStep


def required_starting_materials(
    route: Route,
    target_grams: float,
    target_mw: float,
    default_yield: float = 0.7,
) -> dict[str, float]:
    """Grams of each purchasable starting material needed to make `target_grams` of the target.

    Works backwards through the route: a reactant that is the product of an earlier
    step is made, not bought, so its requirement is pushed further back.
    """
    if not route.steps:
        return {}
    by_product: dict[str, RouteStep] = {}
    for step in route.steps:
        key = chem.canonical(step.product) or step.product
        by_product[key] = step

    grams_needed: dict[str, float] = defaultdict(float)

    def need_step(step: RouteStep, product_moles: float, path: frozenset[str]) -> None:
        y = step.yield_ if step.yield_ and step.yield_ > 0 else default_yield
        moles_per_reactant = product_moles / y
        for i, reactant in enumerate(step.reactants):
            eq = (step.equivalents[i] if step.equivalents and i < len(step.equivalents) else None) or 1.0
            moles = moles_per_reactant * eq
            key = chem.canonical(reactant) or reactant
            earlier = by_product.get(key)
            if earlier is not None and key not in path:  # made in an earlier step (no cycles)
                need_step(earlier, moles, path | {key})
            else:
                mw = chem.mol_weight(reactant) or 0.0
                grams_needed[key] += moles * mw

    final_step = route.steps[-1]
    final_key = chem.canonical(final_step.product) or final_step.product
    need_step(final_step, target_grams / target_mw, frozenset({final_key}))
    return dict(grams_needed)


def build_cost(
    query: Query,
    buy: Purchase | None,
    materials: list[MaterialCost],
    has_route: bool,
) -> CostBreakdown:
    budget_aud = fx.to_base(query.budget, query.currency) or query.budget

    make_materials = None
    make_total = None
    complete = True
    if has_route and materials:
        priced = [m.line_cost_aud for m in materials if m.priced]
        complete = len(priced) == len(materials)
        make_materials = round(sum(priced), 2)
        make_total = round(make_materials * (1 + query.consumables_margin), 2)

    options: list[tuple[str, float]] = []
    if buy is not None:
        options.append(("buy", buy.total_aud))
    if make_total is not None and complete:
        options.append(("make", make_total))

    cheapest, best = (min(options, key=lambda kv: kv[1]) if options else (None, None))
    return CostBreakdown(
        budget_aud=round(budget_aud, 2),
        buy=buy,
        make_materials_aud=make_materials,
        make_total_aud=make_total,
        make_complete=complete,
        cheapest=cheapest,
        best_cost_aud=best,
        fits_budget=(best <= budget_aud) if best is not None else None,
    )
