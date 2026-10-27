"""The orchestrator: a small explicit state machine.

Each handler reads/updates the RunState and returns the name of the next state.
State is checkpointed to the database after every step so a run can resume
(e.g. after NEEDS_INPUT, when the user picks the right compound).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from core import chem, cost, explain, literature, pricing, repository, resolver, routes
from core.config import get_settings
from core.models import Compound, MaterialCost, Query, RunState, StateName

TERMINAL: set[str] = {"DONE", "NEEDS_INPUT"}

STAGE_LABELS: dict[str, str] = {
    "RESOLVE": "Resolving compound",
    "CHECK_MARKET": "Checking vendors",
    "FIND_KNOWN_ROUTE": "Looking for known routes",
    "SEARCH_LITERATURE": "Searching the literature",
    "PREDICT_ROUTE": "Predicting a route",
    "PRICE_MATERIALS": "Pricing starting materials",
    "COST": "Costing",
    "EXPLAIN": "Writing the summary",
}


@dataclass
class StageEvent:
    kind: str  # "started" | "finished"
    stage: str
    detail: str | None = None
    seconds: float | None = None


# ---------------- handlers ----------------

def resolve_state(state: RunState) -> StateName:
    if state.compound is not None:  # resumed after NEEDS_INPUT
        return "CHECK_MARKET"
    result = resolver.resolve(state.query.raw_input, state.query.input_type)
    if result.compound:
        state.compound = result.compound
        return "CHECK_MARKET"
    state.candidates = result.candidates
    if result.error:
        state.warn(result.error)
    return "NEEDS_INPUT"


def check_market(state: RunState) -> StateName:
    offers, warnings = pricing.get_offers(state.compound, regions=state.query.regions)
    state.offers = offers
    for w in warnings:
        state.warn(w)
    buyable = pricing.cheapest_purchase(offers, state.query.grams, state.query.min_purity) is not None
    if buyable and not state.query.compare_synthesis:
        return "COST"  # buy only
    return "FIND_KNOWN_ROUTE"


def _has_cached_offers(smiles: str) -> bool:
    ik = chem.inchikey(smiles)
    return bool(ik and repository.get_offers(ik))


def find_known_route(state: RunState) -> StateName:
    route = routes.find_known_route(state.compound, state.query.max_steps, is_buyable=_has_cached_offers)
    if route:
        state.route = route
        return "PRICE_MATERIALS"
    if get_settings().literature_enabled:
        return "SEARCH_LITERATURE"
    return _after_known_route(state)


def _after_known_route(state: RunState) -> StateName:
    if state.query.allow_predicted:
        return "PREDICT_ROUTE"
    state.warn("No known synthesis route, and predicted routes are turned off.")
    return "COST"


def search_literature(state: RunState) -> StateName:
    state.literature, warning = literature.find_synthesis_papers(state.compound.name or state.compound.cas or state.compound.smiles)
    if warning:
        state.warn(warning)
    return _after_known_route(state)


def predict_route(state: RunState) -> StateName:
    found, warning = routes.predict_routes(state.compound, state.query.max_steps)
    if warning:
        state.warn(warning)
    if not found:
        return "COST"
    state.route, state.alternative_routes = found[0], found[1:]
    return "PRICE_MATERIALS"


def price_materials(state: RunState) -> StateName:
    mw = state.compound.mol_weight or chem.mol_weight(state.compound.smiles)
    needs = cost.required_starting_materials(
        state.route, state.query.grams, mw, state.query.default_step_yield
    )
    materials: list[MaterialCost] = []
    for smiles, grams in needs.items():
        res = resolver.resolve(smiles, "smiles")
        comp: Compound | None = res.compound
        purchase = None
        is_demo = False
        if comp:
            offers, warnings = pricing.get_offers(comp, regions=state.query.regions)
            for w in warnings:
                state.warn(w)
            purchase = pricing.cheapest_purchase(offers, grams)
            is_demo = bool(purchase and purchase.offer.is_demo)
        if purchase is None:
            state.warn(f"No price found for starting material {comp.label if comp else smiles}.")
        materials.append(
            MaterialCost(
                smiles=smiles,
                inchikey=comp.inchikey if comp else None,
                name=comp.name if comp else None,
                grams_needed=round(grams, 4),
                purchase=purchase,
                is_demo=is_demo,
            )
        )
    state.materials = materials
    return "COST"


def cost_state(state: RunState) -> StateName:
    buy = pricing.cheapest_purchase(state.offers, state.query.grams, state.query.min_purity)
    state.cost = cost.build_cost(state.query, buy, state.materials, has_route=state.route is not None)
    return "EXPLAIN"


def explain_state(state: RunState) -> StateName:
    state.explanation = explain.explain(state)
    return "DONE"


HANDLERS: dict[str, Callable[[RunState], StateName]] = {
    "RESOLVE": resolve_state,
    "CHECK_MARKET": check_market,
    "FIND_KNOWN_ROUTE": find_known_route,
    "SEARCH_LITERATURE": search_literature,
    "PREDICT_ROUTE": predict_route,
    "PRICE_MATERIALS": price_materials,
    "COST": cost_state,
    "EXPLAIN": explain_state,
}


# ---------------- loop ----------------

def run(
    state: RunState,
    on_event: Callable[[StageEvent], None] = lambda e: None,
    checkpoint: bool = True,
) -> RunState:
    state.status = "running"
    while state.current not in TERMINAL:
        stage = state.current
        on_event(StageEvent("started", stage))
        t0 = time.perf_counter()
        state.current = HANDLERS[stage](state)
        dt = round(time.perf_counter() - t0, 3)
        state.timings[stage] = dt
        on_event(StageEvent("finished", stage, seconds=dt))
        if checkpoint:
            repository.save_run(state)
    state.status = "done" if state.current == "DONE" else "needs_input"
    if checkpoint:
        repository.save_run(state)
    return state


def start(query: Query, **kwargs) -> RunState:
    return run(RunState(query=query), **kwargs)


def resume_with_compound(state: RunState, compound: Compound, **kwargs) -> RunState:
    """Continue a NEEDS_INPUT run after the user picked a compound."""
    repository.upsert_compound(compound, synonyms=[state.query.raw_input])
    state.compound = compound
    state.candidates = []
    state.current = "CHECK_MARKET"
    return run(state, **kwargs)


def recost(state: RunState, query: Query) -> RunState:
    """Re-run only the cost/explain stages after the user edits assumptions in the report."""
    state.query = query
    if state.route:
        state.current = "PRICE_MATERIALS"
    else:
        state.current = "COST"
    return run(state, checkpoint=True)
