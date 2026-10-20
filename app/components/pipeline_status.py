"""Run the pipeline inside st.status so each state shows up as live progress."""

from __future__ import annotations

from typing import Callable

import streamlit as st

from core.models import RunState
from core.pipeline import STAGE_LABELS, StageEvent


def run_with_status(fn: Callable[..., RunState], *args, **kwargs) -> RunState:
    with st.status("Running analysis…", expanded=True) as status:
        placeholders: dict[str, st.delta_generator.DeltaGenerator] = {}

        def on_event(e: StageEvent) -> None:
            label = STAGE_LABELS.get(e.stage, e.stage)
            if e.kind == "started":
                placeholders[e.stage] = st.empty()
                placeholders[e.stage].markdown(f":material/progress_activity: {label}…")
            else:
                placeholders[e.stage].markdown(f":material/check: {label} ({e.seconds:.1f}s)")

        state = fn(*args, on_event=on_event, **kwargs)
        if state.status == "needs_input":
            status.update(label="Need your input", state="error", expanded=True)
        else:
            status.update(label="Analysis complete", state="complete", expanded=False)
    return state
