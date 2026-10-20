"""Data admin: vendor health, coverage, exchange rates, manual re-scrape."""

from datetime import datetime

import pandas as pd
import streamlit as st

from app.components import offers_table
from core import fx, repository, resolver
from core.config import get_settings
from core.pricing import scrape_compound
from scrapers.registry import get_scraper
from scrapers.vendors import VENDORS

st.title("Data admin")
settings = get_settings()

m1, m2, m3 = st.columns(3)
m1.metric("Compounds priced", repository.priced_compound_count())
m2.metric("Offers stored", repository.offer_count())
m3.metric("Known reactions", repository.reaction_count())

# ---------- vendors ----------
st.subheader("Vendors")
stats = {r["key"]: r for r in repository.list_vendor_rows()}
enabled = set(settings.enabled_vendor_keys)
rows = []
for v in VENDORS:
    s = stats.get(v.key, {})
    rows.append(
        {
            "Vendor": v.name,
            "Key": v.key,
            "Region": v.region,
            "Enabled": v.key in enabled,
            "Search URL verified": v.verified,
            "Needs browser": v.requires_js,
            "Last scrape": s.get("last_scrape_at"),
            "Last OK": s.get("last_scrape_ok"),
            "Success rate": s.get("success_rate"),
            "Offers": s.get("offers", 0),
            "Last error": s.get("last_error"),
        }
    )
st.dataframe(
    pd.DataFrame(rows),
    hide_index=True,
    width="stretch",
    column_config={"Success rate": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")},
)
st.caption("Enable vendors with ENABLED_VENDORS in .env. Verify each search URL in scrapers/vendors.py first.")

# ---------- manual scrape ----------
st.subheader("Re-scrape a compound")
with st.form("rescrape"):
    term = st.text_input("Name, CAS or SMILES")
    keys = st.multiselect("Vendors", [v.key for v in VENDORS], default=[k for k in settings.enabled_vendor_keys])
    go = st.form_submit_button("Scrape now")
if go and term:
    res = resolver.resolve(term)
    if not res.compound:
        st.error(res.error or "Ambiguous name; use CAS or SMILES.")
    else:
        with st.spinner(f"Scraping {len(keys)} vendors for {res.compound.label}…"):
            offers, warnings = scrape_compound(res.compound, [get_scraper(k) for k in keys])
        offers_table(offers)
        for w in warnings:
            st.warning(w)

# ---------- fx ----------
st.subheader("Exchange rates")
rates = fx.cached_rates()
if rates:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Currency": cur,
                    f"→ {settings.base_currency}": r["rate"],
                    "Fetched": datetime.fromtimestamp(r["fetched_at"]),
                    "Source": "fallback (approx.)" if r["fallback"] else "Frankfurter (ECB)",
                }
                for cur, r in rates.items()
            ]
        ),
        hide_index=True,
    )
else:
    st.caption("No rates fetched yet in this session.")

# ---------- demo data ----------
st.subheader("Demo data")
if st.button("Reload sample data"):
    from scripts.seed_demo import load_demo

    st.success(f"Loaded {load_demo()}")
