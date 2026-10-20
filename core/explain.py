"""EXPLAIN: a short, plain-language explanation of the verdict.

Claude only writes the words. Every number comes from the cost model and is passed in.
"""

from __future__ import annotations

import json

from core import llm
from core.models import RunState

SYSTEM = (
    "You write the summary paragraph of a chemical cost report for a researcher. "
    "Use only the numbers provided; never invent prices, yields or vendors. "
    "2-4 sentences, plain English, AUD. Mention the main cost driver and any caveat "
    "(unpriced materials, predicted route, quote-only offers, sample data)."
)


def _facts(state: RunState) -> dict:
    c = state.cost
    return {
        "compound": state.compound.label if state.compound else state.query.raw_input,
        "quantity": f"{state.query.quantity} {state.query.quantity_unit}",
        "min_purity_percent": state.query.min_purity,
        "budget_aud": c.budget_aud if c else None,
        "buy": {
            "vendor": c.buy.offer.vendor,
            "packs": f"{c.buy.n_packs} x {c.buy.offer.pack_qty:g} {c.buy.offer.pack_unit}",
            "total_aud": c.buy.total_aud,
        }
        if c and c.buy
        else None,
        "quote_only_vendors": sorted({o.vendor for o in state.offers if o.quote_only}),
        "route_source": state.route.source if state.route else None,
        "route_steps": len(state.route.steps) if state.route else 0,
        "make_total_aud": c.make_total_aud if c else None,
        "make_complete": c.make_complete if c else None,
        "unpriced_materials": [m.name or m.smiles for m in state.materials if not m.priced],
        "most_expensive_material": max(
            (m for m in state.materials if m.priced), key=lambda m: m.line_cost_aud or 0, default=None
        ).name if any(m.priced for m in state.materials) else None,
        "cheapest_option": c.cheapest if c else None,
        "best_cost_aud": c.best_cost_aud if c else None,
        "fits_budget": c.fits_budget if c else None,
        "uses_sample_data": state.uses_demo_data,
        "warnings": state.warnings[:5],
    }


def template_explanation(state: RunState) -> str:
    c = state.cost
    name = state.compound.label if state.compound else "This compound"
    if c is None or c.best_cost_aud is None:
        parts = [f"We couldn't find a complete price for {name}."]
        if state.offers and all(o.quote_only for o in state.offers):
            parts.append("Vendors list it, but only on request for a quote.")
        if state.materials and c is not None and not c.make_complete:
            parts.append("Some starting materials for the synthesis route have no price yet.")
        return " ".join(parts)
    how = "buying it" if c.cheapest == "buy" else "making it from the route's starting materials"
    verdict = "fits within" if c.fits_budget else "exceeds"
    text = (
        f"The cheapest option for {state.query.quantity:g} {state.query.quantity_unit} of {name} is {how}, "
        f"at about A${c.best_cost_aud:,.2f}, which {verdict} the A${c.budget_aud:,.2f} budget"
    )
    gap = abs(c.gap_aud or 0)
    text += f" by A${gap:,.2f}." if gap else "."
    if c.cheapest == "make" and state.route and state.route.source == "predicted":
        text += " The route is AI-predicted, so treat the cost as a rough estimate."
    if state.uses_demo_data:
        text += " Some prices are sample data, not live quotes."
    return text


def explain(state: RunState) -> str:
    text = llm.complete(
        "Write the summary for these results:\n" + json.dumps(_facts(state), default=str, indent=2),
        system=SYSTEM,
        max_tokens=300,
    )
    return text or template_explanation(state)
