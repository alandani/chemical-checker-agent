"""New analysis: enter a compound + requirements, confirm the compound, run the pipeline."""

import streamlit as st

from app import state as ss
from app.components import compound_card, run_with_status
from core import pipeline, resolver
from core.config import get_settings
from core.models import Query, RunState
from scrapers.registry import all_regions

st.title("New analysis")
st.caption("Can I afford this compound, and should I buy it or make it?")

settings = get_settings()

# ---------- 1. compound input ----------
st.subheader("1. Compound")
method = st.radio(
    "Input method", ["Name / CAS", "SMILES", "Draw"], horizontal=True, label_visibility="collapsed"
)
raw_input = ""
input_type = "auto"
if method == "Name / CAS":
    raw_input = st.text_input("Name or CAS number", placeholder="e.g. Topiramate or 97240-79-4")
elif method == "SMILES":
    raw_input = st.text_input("SMILES", placeholder="e.g. O=C(NCc1ccccc1)c1ccccc1")
    input_type = "smiles"
else:
    try:
        from streamlit_ketcher import st_ketcher

        raw_input = st_ketcher(height=420) or ""
        input_type = "smiles"
        if raw_input:
            st.caption(f"SMILES: `{raw_input}`")
    except ImportError:
        st.warning("Install `streamlit-ketcher` to draw structures. Use SMILES for now.")

if st.button("Find compound", icon=":material/search:", disabled=not raw_input.strip()):
    ss.clear_lookup()
    with st.spinner("Looking up compound…"):
        res = resolver.resolve(raw_input, input_type)
    if res.compound:
        ss.set_compound(res.compound)
    elif res.candidates:
        ss.set_candidates(res.candidates)
    else:
        st.error(res.error or "Compound not found.")

candidates = ss.get_candidates()
if candidates and not ss.get_compound():
    st.warning("That name matches more than one compound. Pick the right one:")
    labels = [f"{c.label} — {c.formula or ''} — CAS {c.cas or '?'}" for c in candidates]
    idx = st.radio("Candidates", range(len(candidates)), format_func=lambda i: labels[i])
    compound_card(candidates[idx])
    if st.button("Use this compound"):
        ss.set_compound(candidates[idx])
        ss.set_candidates([])
        st.rerun()

compound = ss.get_compound()
if compound:
    st.markdown("**Is this the right compound?**")
    compound_card(compound)

# ---------- 2. requirements ----------
st.subheader("2. Requirements")
with st.form("requirements"):
    c1, c2, c3 = st.columns(3)
    quantity = c1.number_input("Quantity", min_value=0.001, value=1.0, step=0.5, format="%.3f")
    unit = c1.selectbox("Unit", ["mg", "g", "kg"], index=1)
    min_purity = c2.number_input("Minimum purity (%)", min_value=0.0, max_value=100.0, value=95.0, step=0.5)
    budget = c3.number_input("Budget", min_value=0.0, value=500.0, step=50.0)
    currency = c3.selectbox("Currency", ["AUD", "USD", "EUR", "GBP", "JPY", "CNY"], index=0)

    with st.expander("Advanced options"):
        regions = st.multiselect("Vendor regions (empty = all)", all_regions())
        compare = st.checkbox("Also cost a synthesis route when the compound can be bought", value=False)
        allow_pred = st.checkbox("Allow AI-predicted routes", value=True)
        max_steps = st.slider("Maximum synthesis steps", 1, 8, 5)
        margin = st.slider("Solvents and consumables margin", 0.0, 1.0, 0.15, 0.05, format="%.2f")
        step_yield = st.slider("Assumed yield per step (when unknown)", 0.1, 1.0, 0.7, 0.05)

    submitted = st.form_submit_button(
        "Run analysis", type="primary", icon=":material/play_arrow:", disabled=compound is None
    )

if compound is None:
    st.caption("Find and confirm the compound first.")

if not settings.llm_enabled:
    st.caption(
        ":material/info: No ANTHROPIC_API_KEY set: live price extraction and Claude summaries are off; "
        "cached and sample data still work."
    )

if submitted and compound:
    query = Query(
        raw_input=raw_input or compound.label,
        input_type=input_type,
        quantity=quantity,
        quantity_unit=unit,
        min_purity=min_purity or None,
        budget=budget,
        currency=currency,
        regions=regions or None,
        allow_predicted=allow_pred,
        compare_synthesis=compare,
        max_steps=max_steps,
        consumables_margin=margin,
        default_step_yield=step_yield,
    )
    ss.set_query(query)
    run_state = RunState(query=query, compound=compound)
    result = run_with_status(pipeline.run, run_state)
    ss.set_result(result)
    if result.status == "done":
        st.switch_page("views/report.py")
    else:
        for w in result.warnings:
            st.warning(w)
