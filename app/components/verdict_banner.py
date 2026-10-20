from __future__ import annotations

import streamlit as st

from core.models import RunState


def verdict_banner(state: RunState) -> None:
    c = state.cost
    if c is None or c.fits_budget is None:
        st.warning("Couldn't work out a complete cost", icon=":material/help:")
    elif c.fits_budget:
        st.success(f"Fits budget, with A${c.gap_aud:,.2f} to spare", icon=":material/check_circle:")
    else:
        st.error(f"Over budget by A${abs(c.gap_aud):,.2f}", icon=":material/error:")

    if state.explanation:
        st.markdown(state.explanation.replace("$", "\\$"))
    if state.uses_demo_data:
        st.info("Some prices on this report are sample data, not live quotes.", icon=":material/info:")

    if c:
        m1, m2, m3 = st.columns(3)
        m1.metric("Cost to buy", f"A${c.buy.total_aud:,.2f}" if c.buy else "—")
        make = f"A${c.make_total_aud:,.2f}" if c.make_total_aud is not None else "—"
        m2.metric("Cost to make", make + ("" if c.make_complete else " *"),
                  help=None if c.make_complete else "Some starting materials are unpriced")
        m3.metric("Budget", f"A${c.budget_aud:,.2f}")
