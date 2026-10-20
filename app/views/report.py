"""Report: verdict, market availability, synthesis route, assumptions, export."""

import pandas as pd
import streamlit as st

from app import state as ss
from app.components import compound_card, offers_table, route_view, verdict_banner
from app.components.export import materials_csv, offers_csv, report_html
from core import pipeline, pricing

result = ss.get_result()
if result is None:
    st.title("Report")
    st.info("No analysis yet. Start one on the New analysis page, or open a past run from History.")
    st.stop()

q = result.query
st.title(f"Report: {result.compound.label if result.compound else q.raw_input}")
st.caption(
    f"{q.quantity:g} {q.quantity_unit} · min purity {q.min_purity or '—'}% · "
    f"budget {q.budget:,.2f} {q.currency} · run {str(result.run_id)[:8]} · {result.created_at:%Y-%m-%d %H:%M} UTC"
)

# ---------- summary ----------
with st.container(border=True):
    st.subheader("Summary")
    verdict_banner(result)

if result.compound:
    compound_card(result.compound, image_size=(260, 180))

# ---------- market ----------
st.subheader("Availability in the market")
best = pricing.cheapest_purchase(result.offers, q.grams, q.min_purity)
offers_table(result.offers, best)

# ---------- route ----------
if result.route:
    title = "Established synthesis route" if result.route.source == "known" else "Predicted synthesis route"
    st.subheader(title)
    route_view(result.route, result.materials, q.default_step_yield)
elif result.query.compare_synthesis or not result.offers:
    st.subheader("Synthesis route")
    st.info("No synthesis route found.")

# ---------- buy vs make ----------
c = result.cost
if c and c.buy and c.make_total_aud is not None:
    st.subheader("Buy vs make")
    chart = pd.DataFrame(
        {"Option": ["Buy", "Make", "Budget"], "A$": [c.buy.total_aud, c.make_total_aud, c.budget_aud]}
    ).set_index("Option")
    st.bar_chart(chart, horizontal=True)

# ---------- assumptions ----------
if result.route:
    with st.expander("Assumptions (edit and recalculate)"):
        with st.form("assumptions"):
            y = st.slider("Yield per step when unknown", 0.1, 1.0, q.default_step_yield, 0.05)
            m = st.slider("Solvents and consumables margin", 0.0, 1.0, q.consumables_margin, 0.05)
            qty = st.number_input(f"Quantity ({q.quantity_unit})", min_value=0.001, value=float(q.quantity))
            if st.form_submit_button("Recalculate"):
                new_q = q.model_copy(update={"default_step_yield": y, "consumables_margin": m, "quantity": qty})
                with st.spinner("Recalculating…"):
                    ss.set_result(pipeline.recost(result, new_q))
                st.rerun()

# ---------- notes + export ----------
if result.warnings:
    with st.expander(f"Notes ({len(result.warnings)})"):
        for w in result.warnings:
            st.markdown(f"- {w}")

st.subheader("Export")
e1, e2, e3 = st.columns(3)
name = (result.compound.label if result.compound else "report").replace(" ", "_")
e1.download_button("Report (HTML, print to PDF)", report_html(result), f"{name}_report.html", "text/html")
e2.download_button("Offers (CSV)", offers_csv(result), f"{name}_offers.csv", "text/csv")
if result.materials:
    e3.download_button("Materials (CSV)", materials_csv(result), f"{name}_materials.csv", "text/csv")
