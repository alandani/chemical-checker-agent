"""Typed helpers around st.session_state."""

from __future__ import annotations

import streamlit as st

from core.models import Compound, Query, RunState

_RESULT = "result"
_COMPOUND = "compound"
_CANDIDATES = "candidates"
_QUERY = "query"


def get_result() -> RunState | None:
    return st.session_state.get(_RESULT)


def set_result(state: RunState) -> None:
    st.session_state[_RESULT] = state


def get_compound() -> Compound | None:
    return st.session_state.get(_COMPOUND)


def set_compound(c: Compound | None) -> None:
    st.session_state[_COMPOUND] = c


def get_candidates() -> list[Compound]:
    return st.session_state.get(_CANDIDATES, [])


def set_candidates(cands: list[Compound]) -> None:
    st.session_state[_CANDIDATES] = cands


def get_query() -> Query | None:
    return st.session_state.get(_QUERY)


def set_query(q: Query) -> None:
    st.session_state[_QUERY] = q


def clear_lookup() -> None:
    for key in (_COMPOUND, _CANDIDATES):
        st.session_state.pop(key, None)
