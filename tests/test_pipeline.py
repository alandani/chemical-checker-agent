import pytest

from core import chem, pipeline
from core.cost import required_starting_materials
from core.models import Query, Route, RouteStep, RunState


def test_required_materials_two_step_route():
    # ethanol + benzoic acid -> ethyl benzoate (50%); ester + methylamine (2 eq) -> N-methylbenzamide (100%)
    ester = "CCOC(=O)c1ccccc1"
    route = Route(
        source="known",
        steps=[
            RouteStep(reactants=["CCO", "OC(=O)c1ccccc1"], product=ester, yield_=0.5),
            RouteStep(reactants=[ester, "CN"], product="CNC(=O)c1ccccc1", equivalents=[1, 2], yield_=1.0),
        ],
    )
    mw_p = chem.mol_weight("CNC(=O)c1ccccc1")
    need = required_starting_materials(route, target_grams=mw_p, target_mw=mw_p)  # 1 mol product
    # 1 mol ester (made, not bought) + 2 mol methylamine; ester needs 1/0.5 = 2 mol of each reactant
    assert set(need) == {chem.canonical(s) for s in ["CN", "CCO", "OC(=O)c1ccccc1"]}
    assert need[chem.canonical("CN")] == pytest.approx(2 * chem.mol_weight("CN"))
    assert need[chem.canonical("CCO")] == pytest.approx(2 * chem.mol_weight("CCO"))


def test_cyclic_route_does_not_explode():
    route = Route(
        source="known",
        steps=[
            RouteStep(reactants=["CCO", "CC(=O)O"], product="CCOC(C)=O", yield_=0.5),
            RouteStep(reactants=["CCOC(C)=O", "O"], product="CC(=O)O", yield_=1.0),
        ],
    )
    mw = chem.mol_weight("CC(=O)O")
    need = required_starting_materials(route, target_grams=mw, target_mw=mw)
    assert need[chem.canonical("CC(=O)O")] == pytest.approx(2 * mw)  # bought, not recursed


def test_buy_only_path():
    s = pipeline.start(Query(raw_input="Topiramate", quantity=2, budget=300), checkpoint=False)
    assert s.status == "done"
    assert s.route is None  # buyable, so routes are skipped
    assert s.cost.cheapest == "buy" and s.cost.fits_budget
    assert "FIND_KNOWN_ROUTE" not in s.timings


def test_compare_synthesis_uses_known_route():
    s = pipeline.start(
        Query(raw_input="97240-79-4", quantity=10, budget=300, compare_synthesis=True), checkpoint=False
    )
    assert s.route and s.route.source == "known" and len(s.route.steps) == 2
    names = {m.name for m in s.materials}
    assert names == {"D-Fructose", "Acetone", "Sulfamoyl chloride"}
    assert s.cost.make_complete and s.cost.make_total_aud > 0


def test_not_buyable_goes_to_route():
    s = pipeline.start(Query(raw_input="O=C(NCc1ccccc1)c1ccccc1", quantity=50, budget=200), checkpoint=False)
    assert s.offers == [] and s.route is not None
    assert s.cost.cheapest == "make"


def test_unknown_name_needs_input(monkeypatch):
    from core import resolver

    monkeypatch.setattr(resolver, "_pubchem_lookup", lambda ns, term: [])
    s = pipeline.start(Query(raw_input="definitely-not-a-chemical", budget=1), checkpoint=False)
    assert s.status == "needs_input" and s.warnings


def test_resume_after_needs_input():
    from core import repository

    s = RunState(query=Query(raw_input="something", quantity=1, budget=500), current="NEEDS_INPUT")
    compound = repository.find_compound_local("Topiramate")
    s = pipeline.resume_with_compound(s, compound, checkpoint=False)
    assert s.status == "done" and s.compound.name == "Topiramate"


def test_run_is_saved_and_reloaded():
    from core import repository

    s = pipeline.start(Query(raw_input="Topiramate", quantity=1, budget=100))
    loaded = repository.load_run(str(s.run_id))
    assert loaded and loaded.cost.best_cost_aud == s.cost.best_cost_aud
