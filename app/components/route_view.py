from __future__ import annotations

import pandas as pd
import streamlit as st

from core import chem
from core.models import MaterialCost, Route


@st.cache_data(show_spinner=False)
def _rxn_png(rxn_smiles: str) -> bytes | None:
    return chem.reaction_png(rxn_smiles)


def materials_dataframe(materials: list[MaterialCost]) -> pd.DataFrame:
    rows = []
    for m in materials:
        p = m.purchase
        rows.append(
            {
                "Material": m.name or m.smiles,
                "Needed (g)": round(m.grams_needed, 3),
                "Best vendor": (p.offer.vendor + (" (sample)" if p.offer.is_demo else "")) if p else "No price found",
                "Buy": f"{p.n_packs} × {p.offer.pack_qty:g} {p.offer.pack_unit}" if p else "—",
                "A$ / g": p.offer.price_aud_per_g if p else None,
                "Line cost A$": p.total_aud if p else None,
                "Link": p.offer.url if p else None,
            }
        )
    return pd.DataFrame(rows)


def route_view(route: Route, materials: list[MaterialCost], default_yield: float) -> None:
    badge = ":green-badge[Known route]" if route.source == "known" else ":orange-badge[AI-predicted route]"
    st.markdown(f"{badge} &nbsp; {len(route.steps)} step(s)")
    if route.notes:
        st.caption(route.notes)
    for i, step in enumerate(route.steps, start=1):
        with st.container(border=True):
            st.markdown(f"**Step {i}**")
            png = _rxn_png(step.reaction_smiles)
            if png:
                st.image(png)
            else:
                st.code(step.reaction_smiles)
            y = f"{step.yield_:.0%}" if step.yield_ else f"{default_yield:.0%} (assumed)"
            details = [f"Yield: {y}"]
            if step.conditions:
                details.append(f"Conditions: {step.conditions}")
            if step.reference:
                details.append(f"Source: {step.reference}")
            st.caption(" · ".join(details))

    st.markdown("**Starting materials**")
    if not materials:
        st.info("No starting materials to price.")
        return
    st.dataframe(
        materials_dataframe(materials),
        hide_index=True,
        width="stretch",
        column_config={
            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
            "A$ / g": st.column_config.NumberColumn(format="%.2f"),
            "Line cost A$": st.column_config.NumberColumn(format="%.2f"),
        },
    )
