"""Report exports: a self-contained HTML report (print to PDF from the browser) and CSV tables."""

from __future__ import annotations

import csv
import html
import io

from core import chem
from core.models import MaterialCost, Offer, RunState


def offer_rows(offers: list[Offer]) -> list[dict]:
    rows = []
    for o in sorted(offers, key=lambda o: (o.price_aud_per_g is None, o.price_aud_per_g or 0)):
        rows.append(
            {
                "Vendor": o.vendor + (" (sample)" if o.is_demo else ""),
                "Pack": f"{o.pack_qty:g} {o.pack_unit}" if o.pack_qty and o.pack_unit else "",
                "Price": "Request quote" if o.quote_only else (f"{o.price:.2f} {o.currency}" if o.price is not None else ""),
                "AUD per pack": f"{o.price_aud:.2f}" if o.price_aud is not None else "",
                "AUD per g": f"{o.price_aud_per_g:.2f}" if o.price_aud_per_g is not None else "",
                "Purity %": "" if o.purity is None else f"{o.purity:g}",
                "In stock": {True: "Yes", False: "No"}.get(o.in_stock, ""),
                "Link": o.url or "",
            }
        )
    return rows


def material_rows(materials: list[MaterialCost]) -> list[dict]:
    rows = []
    for m in materials:
        p = m.purchase
        rows.append(
            {
                "Material": m.name or m.smiles,
                "Needed (g)": f"{m.grams_needed:.3f}",
                "Best vendor": (p.offer.vendor + (" (sample)" if p.offer.is_demo else "")) if p else "No price found",
                "Buy": f"{p.n_packs} x {p.offer.pack_qty:g} {p.offer.pack_unit}" if p else "",
                "AUD per g": f"{p.offer.price_aud_per_g:.2f}" if p and p.offer.price_aud_per_g else "",
                "Line cost AUD": f"{p.total_aud:.2f}" if p else "",
                "Link": (p.offer.url or "") if p else "",
            }
        )
    return rows


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _table(rows: list[dict]) -> str:
    if not rows:
        return ""
    head = "".join(f"<th>{html.escape(k)}</th>" for k in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r.values()) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def report_html(state: RunState) -> str:
    c, comp, q = state.cost, state.compound, state.query
    title = html.escape(comp.label if comp else q.raw_input)
    if c and c.fits_budget is not None:
        verdict = (
            f"Fits the budget with A${c.gap_aud:,.2f} to spare"
            if c.fits_budget
            else f"Over budget by A${abs(c.gap_aud):,.2f}"
        )
    else:
        verdict = "Cost could not be completed"

    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>Cost report: {title}</title>",
        "<style>body{font-family:'IBM Plex Sans',system-ui,sans-serif;max-width:880px;margin:2rem auto;padding:0 1rem;color:#13212C}"
        "h1{font-weight:600;margin-bottom:.25rem}h2{font-size:1.1rem;border-bottom:1px solid #D3DDE4;padding-bottom:.3rem;margin-top:2rem}"
        "table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #D3DDE4;padding:6px 8px;text-align:left}"
        "th{color:#5A6B79;font-weight:500}.mol svg{max-width:320px;height:auto}.rxn svg{max-width:100%;height:auto}"
        ".verdict{font-size:1.25rem;font-weight:600}</style></head><body>",
        f"<h1>{title}</h1>",
        f"<p>{q.quantity:g} {q.quantity_unit}, minimum purity {q.min_purity or 'any'}%, budget A${c.budget_aud:,.2f}</p>" if c else "",
        f"<div class='mol'>{chem.mol_svg(comp.smiles) or ''}</div>" if comp else "",
        f"<h2>Summary</h2><p class='verdict'>{html.escape(verdict)}</p><p>{html.escape(state.explanation or '')}</p>",
    ]
    if state.uses_demo_data:
        parts.append("<p><em>Some prices are sample data, not live quotes.</em></p>")
    parts.append("<h2>Availability in the market</h2>")
    parts.append(_table(offer_rows(state.offers)) or "<p>Not sold by the vendors checked.</p>")
    if state.route:
        label = "Established synthesis route" if state.route.source == "known" else "Predicted synthesis route"
        parts.append(f"<h2>{label}</h2>")
        for i, step in enumerate(state.route.steps, 1):
            parts.append(f"<p><strong>Step {i}.</strong> {html.escape(step.conditions or '')}</p>")
            parts.append(f"<div class='rxn'>{chem.reaction_svg(step.reaction_smiles) or ''}</div>")
        parts.append(_table(material_rows(state.materials)))
    if state.warnings:
        parts.append("<h2>Notes</h2><ul>" + "".join(f"<li>{html.escape(w)}</li>" for w in state.warnings) + "</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)
