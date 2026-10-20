from __future__ import annotations

import pandas as pd
import streamlit as st

from core.models import Offer, Purchase


def offers_dataframe(offers: list[Offer]) -> pd.DataFrame:
    rows = []
    for o in offers:
        rows.append(
            {
                "Vendor": o.vendor + (" (sample)" if o.is_demo else ""),
                "Pack": f"{o.pack_qty:g} {o.pack_unit}" if o.pack_qty and o.pack_unit else "—",
                "Price": "Request quote" if o.quote_only else (f"{o.price:,.2f} {o.currency}" if o.price is not None else "—"),
                "A$ / pack": o.price_aud,
                "A$ / g": o.price_aud_per_g,
                "Purity %": o.purity,
                "In stock": {True: "Yes", False: "No"}.get(o.in_stock, "—"),
                "Link": o.url,
                "Scraped": o.scraped_at.strftime("%Y-%m-%d") if not o.is_demo else "sample",
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="A$ / g", na_position="last")
    return df


def offers_table(offers: list[Offer], best: Purchase | None = None) -> None:
    if not offers:
        st.info("Not commercially available from the vendors we checked.")
        return
    if best:
        st.caption(
            f"Cheapest for your quantity: **{best.offer.vendor}**, "
            f"{best.n_packs} × {best.offer.pack_qty:g} {best.offer.pack_unit} = **A\\${best.total_aud:,.2f}**"
        )
    st.dataframe(
        offers_dataframe(offers),
        hide_index=True,
        width="stretch",
        column_config={
            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
            "A$ / pack": st.column_config.NumberColumn(format="%.2f"),
            "A$ / g": st.column_config.NumberColumn(format="%.2f"),
        },
    )
