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


def _mock_valency(monkeypatch, handler):
    import httpx

    from core import literature
    from core.config import get_settings

    monkeypatch.setenv("VALENCY_TOKEN", "test-token")
    get_settings.cache_clear()
    real = literature.ValencyClient
    monkeypatch.setattr(
        literature, "ValencyClient", lambda tok, url, timeout=20: real(tok, url, timeout, httpx.MockTransport(handler))
    )


def test_literature_step_after_missing_known_route(monkeypatch):
    import json

    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-token"
        if body.get("method") == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-11-25"}})
        if body.get("method") == "tools/call":
            papers = [{"title": "A synthesis of benzamides", "authors": ["A. Chem"], "published": "2021-03-01", "doi": "10.1/x"}]
            text = json.dumps({"papers": papers})
            result = {"result": {"content": [{"type": "text", "text": text}]}}
            sse = f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'id': body['id'], **result})}\n\n"
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse)
        return httpx.Response(202)

    _mock_valency(monkeypatch, handler)
    try:
        s = pipeline.start(Query(raw_input="O=C(NCc1ccccc1)c1ccccc1", quantity=50, budget=200), checkpoint=False)
        # this compound has a known route, so the literature stage is skipped
        assert "SEARCH_LITERATURE" not in s.timings

        s = pipeline.start(Query(raw_input="CCCCCCCCCC(=O)NC", quantity=1, budget=200), checkpoint=False)
        assert [p.title for p in s.literature] == ["A synthesis of benzamides"]
        assert s.literature[0].year == 2021 and s.literature[0].url == "https://doi.org/10.1/x"
    finally:
        monkeypatch.delenv("VALENCY_TOKEN")
        from core.config import get_settings

        get_settings.cache_clear()


def test_literature_failure_is_a_warning(monkeypatch):
    import httpx

    _mock_valency(monkeypatch, lambda request: httpx.Response(401))
    try:
        s = pipeline.start(Query(raw_input="CCCCCCCCCC(=O)NC", quantity=1, budget=200), checkpoint=False)
        assert s.status == "done" and s.literature == []
        assert any("Literature search is unavailable" in w for w in s.warnings)
    finally:
        monkeypatch.delenv("VALENCY_TOKEN")
        from core.config import get_settings

        get_settings.cache_clear()
