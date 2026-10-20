"""The 11 vendors from the project deck.

IMPORTANT: the `search_url` patterns are starting points and have NOT been tested
against the live sites. Before relying on a vendor, open its search page in a browser,
search by CAS number, copy the real URL pattern here, and set `verified=True`.
Some vendors only show prices after login or as "request a quote"; those offers are
stored with quote_only=True rather than dropped.
"""

from scrapers.base import VendorInfo

VENDORS: list[VendorInfo] = [
    VendorInfo(
        key="sigma",
        name="Sigma-Aldrich",
        region="International",
        base_url="https://www.sigmaaldrich.com/AU/en/products/chemistry-and-biochemicals",
        search_url="https://www.sigmaaldrich.com/AU/en/search/{q}?focus=products&term={q}&type=product",
        requires_js=True,
        notes="Prices are loaded by JavaScript and may need a logged-in session.",
    ),
    VendorInfo(
        key="thermofisher",
        name="ThermoFisher",
        region="International",
        base_url="https://www.thermofisher.com/au/en/home/order.html",
        search_url="https://www.thermofisher.com/search/results?query={q}&focusarea=Search%20All",
        requires_js=True,
        notes="Deeply nested catalogue; search by CAS instead of crawling categories.",
    ),
    VendorInfo(
        key="enamine",
        name="Enamine",
        region="International",
        base_url="https://enaminestore.com/categories",
        search_url="https://enaminestore.com/search?q={q}",
        requires_js=True,
        notes="Branching category pages; search by CAS.",
    ),
    VendorInfo(
        key="selleck",
        name="Selleck",
        region="Australia",
        base_url="https://www.selleck.au/",
        search_url="https://www.selleck.au/search.html?searchDTO.searchParam={q}",
        notes="Many branches; search by name or CAS.",
    ),
    VendorInfo(
        key="bldpharm",
        name="BLDPharm",
        region="China & International",
        base_url="https://www.bldpharm.com/",
        search_url="https://www.bldpharm.com/search?keyword={q}",
        requires_js=True,
    ),
    VendorInfo(
        key="accelachem",
        name="AccelaChem",
        region="China",
        base_url="https://www.accelachem.cn/",
        search_url="https://www.accelachem.cn/search?keyword={q}",
    ),
    VendorInfo(
        key="wako",
        name="Wako Fujifilm",
        region="Japan",
        base_url="https://labchem-wako.fujifilm.com/asia/index.html",
        search_url="https://labchem-wako.fujifilm.com/asia/search/?q={q}",
    ),
    VendorInfo(
        key="biosynth",
        name="BioSynth",
        region="Europe (Switzerland)",
        base_url="https://www.biosynth.com/",
        search_url="https://www.biosynth.com/search?query={q}",
        requires_js=True,
    ),
    VendorInfo(
        key="medchemexpress",
        name="MedChemExpress",
        region="USA",
        base_url="https://www.medchemexpress.com/",
        search_url="https://www.medchemexpress.com/search.html?q={q}",
    ),
    VendorInfo(
        key="spex",
        name="SPEX CertiPrep",
        region="USA",
        base_url="https://www.fishersci.com/us/en/brands/I9C8M4ZU/spex-certiprep.html",
        search_url="https://www.fishersci.com/us/en/catalog/search/products?keyword={q}",
        requires_js=True,
        notes="Sold through Fisher Scientific; mostly reference standards.",
    ),
    VendorInfo(
        key="3asenrise",
        name="3ASenrise",
        region="China",
        base_url="https://www.3asenrise.com/front/index.htm",
        search_url="https://www.3asenrise.com/front/search?keyword={q}",
        notes="Focus on organic chemistry products.",
    ),
]

VENDORS_BY_KEY = {v.key: v for v in VENDORS}
