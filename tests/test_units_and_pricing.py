from core.models import Offer
from core.pricing import cheapest_purchase, normalise
from core.resolver import detect_input_type, is_valid_cas
from core.units import parse_pack, to_grams
from scrapers.base import RawOffer


def test_parse_pack():
    assert parse_pack("5g") == (5.0, "g")
    assert parse_pack("100 mg") == (100.0, "mg")
    assert parse_pack("Pack size: 1 KG") == (1.0, "kg")
    assert parse_pack("2,5 g") == (2.5, "g")
    assert parse_pack("Inquire") is None


def test_to_grams():
    assert to_grams(250, "mg") == 0.25
    assert to_grams(1, "kg") == 1000
    assert to_grams(25, "mL") is None
    assert to_grams(25, "mL", density_g_per_ml=0.79) == 25 * 0.79


def test_cas_and_input_detection():
    assert is_valid_cas("97240-79-4")
    assert not is_valid_cas("97240-79-5")
    assert detect_input_type("97240-79-4") == "cas"
    assert detect_input_type("O=C(NCc1ccccc1)c1ccccc1") == "smiles"
    assert detect_input_type("Topiramate") == "name"


def test_resolve_backfills_missing_cas_from_pubchem(monkeypatch):
    from core import repository, resolver
    from core.models import Compound

    compound = Compound(inchikey="X", smiles="CCO", name="Ethanol", pubchem_cid=702)
    calls = {}

    monkeypatch.setattr(repository, "find_compound_local", lambda term: compound)

    def fake_upsert(c, synonyms=None):
        calls["cas"] = c.cas
        compound.cas = c.cas

    monkeypatch.setattr(repository, "upsert_compound", fake_upsert)
    monkeypatch.setattr(resolver, "_pubchem_cas", lambda cid: "64-17-5")

    result = resolver.resolve("Ethanol")
    assert result.compound.cas == "64-17-5"
    assert calls["cas"] == "64-17-5"


def test_normalise_aud():
    o = normalise(RawOffer(pack="5 g", price=100, currency="AUD", purity=98), "V", "IK")
    assert o.pack_grams == 5 and o.price_aud == 100 and o.price_aud_per_g == 20
    q = normalise(RawOffer(pack="10 g", quote_only=True), "V", "IK")
    assert q.quote_only and q.price_aud is None


def _offer(pack_g, price, purity=99, quote=False):
    return Offer(vendor="V", compound_inchikey="IK", pack_qty=pack_g, pack_unit="g", pack_grams=pack_g,
                 price=price, currency="AUD", price_aud=price, purity=purity, quote_only=quote)


def test_cheapest_purchase_whole_packs():
    offers = [_offer(5, 110), _offer(25, 380), _offer(1, 1, quote=True)]
    p = cheapest_purchase(offers, grams=6.8)
    assert p.n_packs == 2 and p.total_aud == 220  # 2 x 5 g beats 1 x 25 g
    p = cheapest_purchase(offers, grams=20)
    assert p.offer.pack_grams == 25 and p.total_aud == 380


def test_purity_filter():
    offers = [_offer(5, 10, purity=90), _offer(5, 50, purity=99)]
    assert cheapest_purchase(offers, 1, min_purity=95).total_aud == 50


def test_vendor_search_urls_and_404():
    from core.models import Compound
    from scrapers.registry import get_scraper

    c = Compound(inchikey="X", smiles="NCc1ccccc1", name="Benzylamine", cas="100-46-9")
    enamine = get_scraper("enamine")
    assert "searchBy=CASs" in enamine.search_url(c)
    assert "searchBy" not in enamine.search_url(c.model_copy(update={"cas": None}))

    mce = get_scraper("medchemexpress")
    mce.fetch = lambda url: None  # vendor answered 404: no such product
    assert mce.search(c) == []


def test_sample_offers_do_not_block_live_search(monkeypatch):
    from core import pricing, repository
    from core.config import get_settings

    compound = repository.find_compound_local("Topiramate")  # has sample offers only
    monkeypatch.setattr(get_settings(), "enable_live_scraping", True)
    called = {}

    def fake_scrape(c, scrapers):
        called["yes"] = True
        return [], ["Fake vendor: timed out"]

    monkeypatch.setattr(pricing, "scrape_compound", fake_scrape)
    offers, warnings = pricing.get_offers(compound)
    assert called and warnings == ["Fake vendor: timed out"]
    assert offers and all(o.is_demo for o in offers)  # samples still shown alongside the warning
