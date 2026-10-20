"""History: past runs, each opening its saved report."""

import pandas as pd
import streamlit as st

from app import state as ss
from core import repository

st.title("History")

runs = repository.list_runs()
if not runs:
    st.info("No runs yet.")
    st.stop()

df = pd.DataFrame(runs)
df["verdict"] = df["fits_budget"].map({True: "Fits", False: "Over budget"}).fillna("—")
st.dataframe(
    df[["created_at", "compound", "status", "verdict", "best_cost_aud", "budget_aud"]],
    hide_index=True,
    width="stretch",
    column_config={
        "created_at": st.column_config.DatetimeColumn("When", format="YYYY-MM-DD HH:mm"),
        "best_cost_aud": st.column_config.NumberColumn("Best cost A$", format="%.2f"),
        "budget_aud": st.column_config.NumberColumn("Budget A$", format="%.2f"),
    },
)

labels = {r["run_id"]: f"{r['created_at']:%Y-%m-%d %H:%M} — {r['compound']}" for r in runs}
choice = st.selectbox("Open a run", list(labels), format_func=labels.get)
if st.button("Open report", type="primary"):
    state = repository.load_run(choice)
    if state:
        ss.set_result(state)
        st.switch_page("views/report.py")
