"""Synthesis routes: known routes from the reactions table, predicted routes from AiZynthFinder."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Callable

from core import chem, llm, repository
from core.config import get_settings
from core.models import Compound, Route, RouteStep

log = logging.getLogger(__name__)


# ---------------- known routes ----------------

def _best_reaction(steps: list[RouteStep]) -> RouteStep:
    return max(steps, key=lambda s: (s.yield_ or 0.0, -len(s.reactants)))


def find_known_route(
    compound: Compound,
    max_steps: int = 5,
    is_buyable: Callable[[str], bool] = lambda smi: False,
) -> Route | None:
    """Build a route by chaining recorded reactions backwards from the target.

    A reactant is expanded further only if it has its own recorded reaction and
    isn't already buyable. Steps are returned in lab order (first step first).
    """
    visited: set[str] = set()

    def expand(smiles: str, depth: int) -> list[RouteStep] | None:
        ik = chem.inchikey(smiles)
        if not ik or ik in visited:
            return None
        visited.add(ik)
        candidates = repository.reactions_for_product(ik)
        if not candidates:
            return None
        step = _best_reaction(candidates)
        earlier: list[RouteStep] = []
        if depth < max_steps:
            for reactant in step.reactants:
                if is_buyable(reactant):
                    continue
                sub = expand(reactant, depth + 1)
                if sub:
                    earlier.extend(sub)
        return earlier + [step]

    steps = expand(compound.smiles, 1)
    if not steps:
        return None
    refs = sorted({s.reference for s in steps if s.reference})
    return Route(source="known", steps=steps, reference="; ".join(refs) or None)


# ---------------- predicted routes (AiZynthFinder) ----------------

@lru_cache
def _aizynth_finder():
    """Load AiZynthFinder once (models are large). Returns None if unavailable."""
    path = get_settings().aizynth_config
    if not path:
        return None
    try:
        from aizynthfinder.aizynthfinder import AiZynthFinder
    except ImportError:
        return None
    finder = AiZynthFinder(configfile=path)
    # Use every stock defined in the config, and the first expansion/filter policy.
    stocks = list(finder.stock.items)
    if stocks:
        finder.stock.select(stocks)
    policies = list(finder.expansion_policy.items)
    if policies:
        finder.expansion_policy.select(policies[0])
    try:
        items = list(finder.filter_policy.items)
        if items:
            finder.filter_policy.select(items[0])
    except Exception:
        pass
    return finder


def aizynth_available() -> bool:
    try:
        return _aizynth_finder() is not None
    except Exception:
        return False


def _tree_to_route(tree, score: float | None) -> Route:
    steps: list[RouteStep] = []
    # reactions() walks from the target down; reverse to get lab order.
    for rxn in tree.reactions():
        reactants = rxn.reactants[0] if rxn.reactants and isinstance(rxn.reactants[0], (tuple, list)) else rxn.reactants
        steps.append(
            RouteStep(
                reactants=[m.smiles for m in reactants],
                product=rxn.mol.smiles,
                reference="AiZynthFinder template",
            )
        )
    steps.reverse()
    return Route(source="predicted", steps=steps, score=score)


def predict_routes(compound: Compound, max_steps: int = 5, top_n: int = 3) -> tuple[list[Route], str | None]:
    """Return (routes best-first, warning)."""
    try:
        finder = _aizynth_finder()
    except Exception as exc:
        return [], f"AiZynthFinder failed to load: {exc}"
    if finder is None:
        return [], (
            "Route prediction is not set up (install aizynthfinder and set AIZYNTH_CONFIG). "
            "See README › Route prediction."
        )
    settings = get_settings()
    try:
        finder.config.search.time_limit = settings.aizynth_time_limit_s
        finder.config.search.max_transforms = max_steps
        finder.target_smiles = compound.smiles
        finder.tree_search()
        finder.build_routes()
        trees = list(finder.routes.reaction_trees)[:top_n]
        scores = finder.routes.scores[:top_n] if hasattr(finder.routes, "scores") else [None] * len(trees)
        routes = []
        for tree, sc in zip(trees, scores):
            value = list(sc.values())[0] if isinstance(sc, dict) and sc else sc
            routes.append(_tree_to_route(tree, float(value) if value is not None else None))
        if not routes:
            return [], "AiZynthFinder found no route within the time limit."
        return rank_routes(compound, routes), None
    except Exception as exc:
        log.exception("AiZynthFinder search failed")
        return [], f"Route prediction failed: {exc}"


def rank_routes(compound: Compound, routes: list[Route]) -> list[Route]:
    """Ask Claude which predicted route is most practical; keep model order if unavailable."""
    if len(routes) < 2 or not get_settings().llm_enabled:
        return routes
    summary = [
        {"index": i, "score": r.score, "steps": [s.reaction_smiles for s in r.steps]}
        for i, r in enumerate(routes)
    ]
    data = llm.extract(
        prompt=(
            f"Target: {compound.label} ({compound.smiles}). These are retrosynthesis routes predicted "
            "by AiZynthFinder. Rank them by practicality for a research lab: fewer steps, common "
            "reagents, no exotic or hazardous intermediates.\n" + json.dumps(summary)
        ),
        tool_name="rank_routes",
        tool_description="Return route indices best-first with a one-sentence reason for the top pick.",
        input_schema={
            "type": "object",
            "properties": {
                "order": {"type": "array", "items": {"type": "integer"}},
                "reason": {"type": "string"},
            },
            "required": ["order", "reason"],
        },
        model=get_settings().claude_model_reasoning,
    )
    if not data:
        return routes
    order = [i for i in data.get("order", []) if 0 <= i < len(routes)]
    order += [i for i in range(len(routes)) if i not in order]
    ranked = [routes[i] for i in order]
    ranked[0].notes = data.get("reason")
    return ranked
