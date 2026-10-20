"""Report export: a self-contained HTML file (print to PDF from the browser) and CSVs."""

from __future__ import annotations

import base64
import html

from app.components.offers_table import offers_dataframe
from app.components.route_view import materials_dataframe
from core import chem
from core.models import RunState


def _img(png: bytes | None) -> str:
    if not png:
        return ""
    return f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}" style="max-width:100%">'


def report_html(state: RunState) -> str:
    c, comp = state.cost, state.compound
    title = html.escape(comp.label if comp else state.query.raw_input)
    verdict = "—"
    if c and c.fits_budget is not None:
        verdict = (
            f"Fits budget (A${c.gap_aud:,.2f} to spare)" if c.fits_budget else f"Over budget by A${abs(c.gap_aud):,.2f}"
        )
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>Cost report – {title}</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;color:#222}"
        "table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccc;padding:4px 8px;text-align:left}"
        "th{background:#1f4e79;color:#fff}h2{color:#1f4e79;border-bottom:2px solid #1f4e79}</style></head><body>",
        f"<h1>{title}</h1>",
        _img(chem.mol_png(comp.smiles)) if comp else "",
        f"<p><b>Quantity:</b> {state.query.quantity:g} {state.query.quantity_unit} · "
        f"<b>Budget:</b> A${c.budget_aud:,.2f}</p>" if c else "",
        f"<h2>Summary</h2><p><b>{html.escape(verdict)}</b></p><p>{html.escape(state.explanation or '')}</p>",
    ]
    if state.uses_demo_data:
        parts.append("<p><i>Some prices are sample data, not live quotes.</i></p>")
    parts.append("<h2>Availability in the market</h2>")
    df = offers_dataframe(state.offers)
    parts.append(df.to_html(index=False, na_rep="—") if not df.empty else "<p>Not commercially available from the vendors checked.</p>")
    if state.route:
        label = "Established synthesis route" if state.route.source == "known" else "Predicted synthesis route"
        parts.append(f"<h2>{label}</h2>")
        for i, step in enumerate(state.route.steps, 1):
            parts.append(f"<p><b>Step {i}</b> {html.escape(step.conditions or '')}</p>")
            parts.append(_img(chem.reaction_png(step.reaction_smiles)))
        parts.append(materials_dataframe(state.materials).to_html(index=False, na_rep="—"))
    if state.warnings:
        parts.append("<h2>Notes</h2><ul>" + "".join(f"<li>{html.escape(w)}</li>" for w in state.warnings) + "</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def offers_csv(state: RunState) -> bytes:
    return offers_dataframe(state.offers).to_csv(index=False).encode()


def materials_csv(state: RunState) -> bytes:
    return materials_dataframe(state.materials).to_csv(index=False).encode()
