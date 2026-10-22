"""Background run manager.

Each analysis runs the pipeline in a worker thread. Stage events are collected in
memory so the browser can follow progress over Server-Sent Events, and the state is
checkpointed to the database by the pipeline itself (so History survives restarts).
"""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass, field

from core import pipeline, repository
from core.models import Compound, Query, RunState
from core.pipeline import StageEvent


@dataclass
class RunHandle:
    state: RunState
    events: list[dict] = field(default_factory=list)
    done: bool = False
    error: str | None = None


_RUNS: dict[str, RunHandle] = {}
_LOCK = threading.Lock()
_MAX_KEPT = 200


def _remember(handle: RunHandle) -> None:
    with _LOCK:
        _RUNS[str(handle.state.run_id)] = handle
        if len(_RUNS) > _MAX_KEPT:  # drop the oldest finished runs from memory
            for key in [k for k, h in _RUNS.items() if h.done][: len(_RUNS) - _MAX_KEPT]:
                _RUNS.pop(key, None)


def get(run_id: str) -> RunHandle | None:
    return _RUNS.get(run_id)


def start(query: Query, compound: Compound | None) -> RunHandle:
    if compound is not None:
        repository.upsert_compound(compound)
    handle = RunHandle(state=RunState(query=query, compound=compound))
    _remember(handle)

    def on_event(e: StageEvent) -> None:
        handle.events.append(
            {"kind": e.kind, "stage": e.stage, "label": pipeline.STAGE_LABELS.get(e.stage, e.stage), "seconds": e.seconds}
        )

    def work() -> None:
        try:
            pipeline.run(handle.state, on_event=on_event)
        except Exception as exc:  # surface the failure to the browser instead of hanging
            traceback.print_exc()
            handle.error = f"{type(exc).__name__}: {exc}"
        finally:
            handle.done = True

    threading.Thread(target=work, name=f"run-{handle.state.run_id}", daemon=True).start()
    return handle
