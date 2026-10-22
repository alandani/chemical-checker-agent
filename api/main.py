"""FastAPI app: JSON API under /api, and the built web frontend (web/dist) at /.

    uvicorn api.main:app --reload            # API on http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query as Q
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import runs
from core import chem, fx, pipeline, report, repository, resolver, routes
from core.config import ROOT_DIR, get_settings
from core.db import init_db
from core.models import Compound, Query, RunState
from core.pricing import scrape_compound
from scrapers.registry import all_regions, get_scraper
from scrapers.vendors import VENDORS

WEB_DIST = ROOT_DIR / "web" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    for v in VENDORS:
        repository.upsert_vendor(v.key, v.name, v.region, v.base_url)
    yield


app = FastAPI(title="Chemical Price Checker API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def dump(state: RunState) -> dict:
    return state.model_dump(mode="json", by_alias=True)


# ---------------- meta ----------------

@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "llm_enabled": s.llm_enabled,
        "live_scraping": s.enable_live_scraping,
        "route_prediction": bool(s.aizynth_config),
        "base_currency": s.base_currency,
        "regions": all_regions(),
    }


# ---------------- compounds ----------------

class ResolveIn(BaseModel):
    raw_input: str
    input_type: Literal["auto", "smiles", "name", "cas"] = "auto"


@app.post("/api/resolve")
def resolve(body: ResolveIn) -> dict:
    res = resolver.resolve(body.raw_input, body.input_type)
    return {
        "compound": res.compound.model_dump(mode="json") if res.compound else None,
        "candidates": [c.model_dump(mode="json") for c in res.candidates],
        "error": res.error,
    }


@lru_cache(maxsize=2048)
def _mol_svg(smiles: str, w: int, h: int, theme: str) -> str | None:
    return chem.mol_svg(smiles, w, h, theme)


@lru_cache(maxsize=1024)
def _rxn_svg(rxn: str, w: int, h: int, theme: str) -> str | None:
    return chem.reaction_svg(rxn, w, h, theme)


SVG_HEADERS = {"Cache-Control": "public, max-age=86400"}


@app.get("/api/svg/molecule")
def molecule_svg(
    smiles: str,
    w: int = Q(360, ge=60, le=1600),
    h: int = Q(260, ge=60, le=1200),
    theme: Literal["light", "dark"] = "light",
) -> Response:
    svg = _mol_svg(smiles, w, h, theme)
    if svg is None:
        raise HTTPException(422, "Could not parse SMILES")
    return Response(svg, media_type="image/svg+xml", headers=SVG_HEADERS)


@app.get("/api/svg/reaction")
def reaction_svg(
    smiles: str,
    w: int = Q(760, ge=200, le=2000),
    h: int = Q(220, ge=80, le=800),
    theme: Literal["light", "dark"] = "light",
) -> Response:
    svg = _rxn_svg(smiles, w, h, theme)
    if svg is None:
        raise HTTPException(422, "Could not parse reaction SMILES")
    return Response(svg, media_type="image/svg+xml", headers=SVG_HEADERS)


# ---------------- runs ----------------

class RunIn(BaseModel):
    query: Query
    compound: Compound | None = None


@app.post("/api/runs", status_code=202)
def create_run(body: RunIn) -> dict:
    handle = runs.start(body.query, body.compound)
    return {"run_id": str(handle.state.run_id)}


def _load(run_id: str) -> RunState:
    handle = runs.get(run_id)
    if handle and handle.done:
        return handle.state
    if handle:
        return handle.state
    state = repository.load_run(run_id)
    if state is None:
        raise HTTPException(404, "Run not found")
    return state


@app.get("/api/runs")
def list_runs(limit: int = 200) -> list[dict]:
    return [
        {**r, "created_at": r["created_at"].isoformat() if r["created_at"] else None}
        for r in repository.list_runs(limit)
    ]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    return dump(_load(run_id))


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    """Server-Sent Events: one `stage` event per stage start/finish, then `done` with the full state."""
    handle = runs.get(run_id)

    async def stream():
        if handle is None:  # finished in a previous server process
            state = repository.load_run(run_id)
            if state is None:
                yield f"event: failed\ndata: {json.dumps({'error': 'Run not found'})}\n\n"
                return
            yield f"event: done\ndata: {json.dumps(dump(state))}\n\n"
            return
        sent = 0
        while True:
            while sent < len(handle.events):
                yield f"event: stage\ndata: {json.dumps(handle.events[sent])}\n\n"
                sent += 1
            if handle.done:
                if handle.error:
                    yield f"event: failed\ndata: {json.dumps({'error': handle.error})}\n\n"
                else:
                    yield f"event: done\ndata: {json.dumps(dump(handle.state))}\n\n"
                return
            await asyncio.sleep(0.15)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


class RecostIn(BaseModel):
    quantity: float | None = None
    default_step_yield: float | None = None
    consumables_margin: float | None = None
    budget: float | None = None


@app.post("/api/runs/{run_id}/recost")
def recost(run_id: str, body: RecostIn) -> dict:
    state = _load(run_id)
    if state.status != "done":
        raise HTTPException(409, "Run is not finished")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    new_state = pipeline.recost(state, state.query.model_copy(update=updates))
    return dump(new_state)


class PickIn(BaseModel):
    compound: Compound


@app.post("/api/runs/{run_id}/compound")
def pick_compound(run_id: str, body: PickIn) -> dict:
    """Resume a run that stopped at NEEDS_INPUT. Returns a new run id to follow."""
    state = _load(run_id)
    handle = runs.start(state.query, body.compound)
    return {"run_id": str(handle.state.run_id)}


@app.get("/api/runs/{run_id}/export/report.html")
def export_html(run_id: str) -> HTMLResponse:
    state = _load(run_id)
    name = (state.compound.label if state.compound else "report").replace(" ", "_")
    return HTMLResponse(
        report.report_html(state), headers={"Content-Disposition": f'attachment; filename="{name}_report.html"'}
    )


@app.get("/api/runs/{run_id}/export/{table}.csv")
def export_csv(run_id: str, table: Literal["offers", "materials"]) -> PlainTextResponse:
    state = _load(run_id)
    rows = report.offer_rows(state.offers) if table == "offers" else report.material_rows(state.materials)
    name = (state.compound.label if state.compound else "report").replace(" ", "_")
    return PlainTextResponse(
        report.to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}_{table}.csv"'},
    )


# ---------------- data admin ----------------

@app.get("/api/admin/overview")
def admin_overview() -> dict:
    s = get_settings()
    stats = {r["key"]: r for r in repository.list_vendor_rows()}
    enabled = set(s.enabled_vendor_keys)
    vendors = []
    for v in VENDORS:
        st = stats.get(v.key, {})
        vendors.append(
            {
                "key": v.key,
                "name": v.name,
                "region": v.region,
                "base_url": v.base_url,
                "enabled": v.key in enabled,
                "verified": v.verified,
                "requires_js": v.requires_js,
                "notes": v.notes,
                "last_scrape_at": st.get("last_scrape_at").isoformat() if st.get("last_scrape_at") else None,
                "last_scrape_ok": st.get("last_scrape_ok"),
                "success_rate": st.get("success_rate"),
                "offers": st.get("offers", 0),
                "last_error": st.get("last_error"),
            }
        )
    return {
        "stats": {
            "compounds_priced": repository.priced_compound_count(),
            "offers": repository.offer_count(),
            "reactions": repository.reaction_count(),
        },
        "vendors": vendors,
        "rates": [
            {"currency": cur, "rate": r["rate"], "fallback": r["fallback"]} for cur, r in fx.cached_rates().items()
        ],
        "route_prediction_ready": routes.aizynth_available() if s.aizynth_config else False,
    }


class ScrapeIn(BaseModel):
    term: str
    vendors: list[str]


@app.post("/api/admin/scrape")
def admin_scrape(body: ScrapeIn) -> dict:
    res = resolver.resolve(body.term)
    if not res.compound:
        raise HTTPException(422, res.error or "That name matches several compounds. Use a CAS number or SMILES.")
    unknown = [k for k in body.vendors if k not in {v.key for v in VENDORS}]
    if unknown:
        raise HTTPException(422, f"Unknown vendor keys: {', '.join(unknown)}")
    offers, warnings = scrape_compound(res.compound, [get_scraper(k) for k in body.vendors])
    return {
        "compound": res.compound.model_dump(mode="json"),
        "offers": [o.model_dump(mode="json") for o in offers],
        "warnings": warnings,
    }


@app.post("/api/admin/demo")
def admin_reload_demo() -> dict:
    from scripts.seed_demo import load_demo

    return load_demo()


# ---------------- web frontend ----------------

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (WEB_DIST / path).resolve()
        if path and candidate.is_file() and WEB_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
