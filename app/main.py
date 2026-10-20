"""Streamlit entry point:  streamlit run app/main.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import repository  # noqa: E402
from core.db import init_db  # noqa: E402
from scrapers.vendors import VENDORS  # noqa: E402

st.set_page_config(page_title="Chemical Price Checker", page_icon="⚗️", layout="wide")


@st.cache_resource
def _bootstrap() -> bool:
    init_db()
    for v in VENDORS:
        repository.upsert_vendor(v.key, v.name, v.region, v.base_url)
    return True


_bootstrap()

nav = st.navigation(
    [
        st.Page("views/new_analysis.py", title="New analysis", icon=":material/science:", default=True),
        st.Page("views/report.py", title="Report", icon=":material/summarize:"),
        st.Page("views/history.py", title="History", icon=":material/history:"),
        st.Page("views/data_admin.py", title="Data admin", icon=":material/database:"),
    ]
)
nav.run()
