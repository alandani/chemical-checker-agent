"""Read/write helpers so the rest of the code never touches ORM rows directly."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select

from core.db import CompoundRow, OfferRow, ReactionRow, RunRow, VendorRow, session_scope
from core.models import Compound, Offer, RouteStep, RunState, utcnow


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- compounds ----------

def upsert_compound(c: Compound, synonyms: list[str] | None = None) -> None:
    with session_scope() as s:
        row = s.get(CompoundRow, c.inchikey) or CompoundRow(inchikey=c.inchikey)
        row.smiles = c.smiles
        row.name = c.name or row.name
        row.cas = c.cas or row.cas
        row.formula = c.formula or row.formula
        row.mol_weight = c.mol_weight or row.mol_weight
        row.pubchem_cid = c.pubchem_cid or row.pubchem_cid
        if synonyms:
            row.synonyms = sorted(set((row.synonyms or []) + synonyms))
        s.merge(row)


def _to_compound(row: CompoundRow) -> Compound:
    return Compound(
        inchikey=row.inchikey,
        smiles=row.smiles,
        name=row.name,
        cas=row.cas,
        formula=row.formula,
        mol_weight=row.mol_weight,
        pubchem_cid=row.pubchem_cid,
    )


def get_compound(inchikey: str) -> Compound | None:
    with session_scope() as s:
        row = s.get(CompoundRow, inchikey)
        return _to_compound(row) if row else None


def find_compound_local(term: str) -> Compound | None:
    """Case-insensitive match on name or CAS in the local cache."""
    t = term.strip().lower()
    with session_scope() as s:
        row = s.scalars(
            select(CompoundRow).where(
                or_(func.lower(CompoundRow.name) == t, CompoundRow.cas == term.strip())
            )
        ).first()
        if row:
            return _to_compound(row)
        # Fall back to synonyms (JSON list) – small table, scan is fine for an MVP.
        for row in s.scalars(select(CompoundRow).where(CompoundRow.synonyms.is_not(None))):
            if any(t == str(syn).lower() for syn in row.synonyms or []):
                return _to_compound(row)
    return None


# ---------- offers ----------

def _to_offer(row: OfferRow) -> Offer:
    return Offer(
        vendor=row.vendor,
        compound_inchikey=row.compound_inchikey,
        pack_qty=row.pack_qty,
        pack_unit=row.pack_unit,
        pack_grams=row.pack_grams,
        price=row.price,
        currency=row.currency,
        price_aud=row.price_aud,
        price_aud_per_g=row.price_aud_per_g,
        purity=row.purity,
        url=row.url,
        in_stock=row.in_stock,
        quote_only=row.quote_only,
        is_demo=row.is_demo,
        scraped_at=_aware(row.scraped_at),
    )


def get_offers(inchikey: str, max_age_days: int | None = None) -> list[Offer]:
    with session_scope() as s:
        q = select(OfferRow).where(OfferRow.compound_inchikey == inchikey)
        rows = s.scalars(q).all()
    offers = [_to_offer(r) for r in rows]
    if max_age_days is not None:
        cutoff = utcnow() - timedelta(days=max_age_days)
        offers = [o for o in offers if o.is_demo or o.scraped_at >= cutoff]
    return offers


def replace_offers(inchikey: str, vendor: str, offers: list[Offer]) -> None:
    """Replace one vendor's offers for one compound with a fresh scrape."""
    with session_scope() as s:
        s.execute(
            delete(OfferRow).where(
                OfferRow.compound_inchikey == inchikey,
                OfferRow.vendor == vendor,
                OfferRow.is_demo.is_(False),
            )
        )
        for o in offers:
            s.add(OfferRow(**o.model_dump()))


def add_offers(offers: list[Offer]) -> None:
    with session_scope() as s:
        for o in offers:
            s.add(OfferRow(**o.model_dump()))


def offer_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(OfferRow)) or 0


def priced_compound_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count(func.distinct(OfferRow.compound_inchikey)))) or 0


# ---------- vendors ----------

def upsert_vendor(key: str, name: str, region: str, base_url: str) -> None:
    with session_scope() as s:
        row = s.get(VendorRow, key) or VendorRow(key=key, scrape_attempts=0, scrape_successes=0)
        row.name, row.region, row.base_url = name, region, base_url
        s.merge(row)


def record_scrape(key: str, ok: bool, error: str | None = None) -> None:
    with session_scope() as s:
        row = s.get(VendorRow, key)
        if not row:
            return
        row.last_scrape_at = utcnow()
        row.last_scrape_ok = ok
        row.last_error = None if ok else (error or "")[:2000]
        row.scrape_attempts = (row.scrape_attempts or 0) + 1
        row.scrape_successes = (row.scrape_successes or 0) + (1 if ok else 0)


def list_vendor_rows() -> list[dict]:
    with session_scope() as s:
        rows = s.scalars(select(VendorRow).order_by(VendorRow.name)).all()
        counts = dict(
            s.execute(select(OfferRow.vendor, func.count()).group_by(OfferRow.vendor)).all()
        )
        return [
            {
                "key": r.key,
                "name": r.name,
                "region": r.region,
                "last_scrape_at": r.last_scrape_at,
                "last_scrape_ok": r.last_scrape_ok,
                "success_rate": (r.scrape_successes / r.scrape_attempts) if r.scrape_attempts else None,
                "offers": counts.get(r.name, 0),
                "last_error": r.last_error,
            }
            for r in rows
        ]


# ---------- reactions ----------

def add_reaction(step: RouteStep, product_inchikey: str, source: str = "uspto") -> None:
    with session_scope() as s:
        s.add(
            ReactionRow(
                product_inchikey=product_inchikey,
                product_smiles=step.product,
                reactants_smiles=".".join(step.reactants),
                equivalents=step.equivalents,
                conditions=step.conditions,
                yield_=step.yield_,
                reference=step.reference,
                source=source,
            )
        )


def reactions_for_product(inchikey: str) -> list[RouteStep]:
    with session_scope() as s:
        rows = s.scalars(select(ReactionRow).where(ReactionRow.product_inchikey == inchikey)).all()
        return [
            RouteStep(
                reactants=r.reactants_smiles.split("."),
                product=r.product_smiles,
                equivalents=r.equivalents,
                conditions=r.conditions,
                yield_=r.yield_,
                reference=r.reference,
            )
            for r in rows
        ]


def reaction_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(ReactionRow)) or 0


# ---------- runs ----------

def save_run(state: RunState) -> None:
    with session_scope() as s:
        row = s.get(RunRow, str(state.run_id)) or RunRow(run_id=str(state.run_id))
        row.created_at = state.created_at
        row.compound_label = state.compound.label if state.compound else state.query.raw_input
        row.inchikey = state.compound.inchikey if state.compound else None
        row.status = state.status
        row.fits_budget = state.cost.fits_budget if state.cost else None
        row.best_cost_aud = state.cost.best_cost_aud if state.cost else None
        row.budget_aud = state.cost.budget_aud if state.cost else None
        row.state_json = state.model_dump_json()
        s.merge(row)


def load_run(run_id: str) -> RunState | None:
    with session_scope() as s:
        row = s.get(RunRow, run_id)
        return RunState.model_validate_json(row.state_json) if row else None


def list_runs(limit: int = 200) -> list[dict]:
    with session_scope() as s:
        rows = s.scalars(select(RunRow).order_by(RunRow.created_at.desc()).limit(limit)).all()
        return [
            {
                "run_id": r.run_id,
                "created_at": r.created_at,
                "compound": r.compound_label,
                "status": r.status,
                "fits_budget": r.fits_budget,
                "best_cost_aud": r.best_cost_aud,
                "budget_aud": r.budget_aud,
            }
            for r in rows
        ]


def recent_run_inchikeys(days: int = 30) -> list[str]:
    cutoff = utcnow() - timedelta(days=days)
    with session_scope() as s:
        rows = s.scalars(
            select(RunRow.inchikey).where(RunRow.created_at >= cutoff, RunRow.inchikey.is_not(None)).distinct()
        ).all()
        return list(rows)
