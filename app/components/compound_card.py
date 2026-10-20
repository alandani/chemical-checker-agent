from __future__ import annotations

import streamlit as st

from core import chem
from core.models import Compound


@st.cache_data(show_spinner=False)
def _png(smiles: str, w: int, h: int) -> bytes | None:
    return chem.mol_png(smiles, (w, h))


def compound_card(compound: Compound, image_size: tuple[int, int] = (300, 220)) -> None:
    with st.container(border=True):
        left, right = st.columns([1, 2])
        png = _png(compound.smiles, *image_size)
        if png:
            left.image(png)
        right.markdown(f"### {compound.label}")
        rows = {
            "CAS": compound.cas or "—",
            "Formula": compound.formula or "—",
            "Mol. weight": f"{compound.mol_weight:.2f} g/mol" if compound.mol_weight else "—",
            "InChIKey": compound.inchikey,
            "PubChem CID": compound.pubchem_cid or "—",
        }
        for k, v in rows.items():
            right.markdown(f"**{k}:** `{v}`")
        right.caption(f"`{compound.smiles}`")
