"""RESOLVE: turn a drawing / SMILES / name / CAS into one standard compound record.

Order: local cache -> RDKit (for SMILES) -> PubChem PUG REST.
"""

from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from core import chem, repository
from core.config import get_settings
from core.models import Compound

CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PROPS = "Title,IUPACName,MolecularFormula,MolecularWeight,InChIKey,IsomericSMILES"


class ResolveResult:
    def __init__(self, compound: Compound | None = None, candidates: list[Compound] | None = None, error: str | None = None):
        self.compound = compound
        self.candidates = candidates or []
        self.error = error


def is_valid_cas(cas: str) -> bool:
    if not CAS_RE.match(cas):
        return False
    digits = cas.replace("-", "")
    check = int(digits[-1])
    body = digits[:-1][::-1]
    return sum((i + 1) * int(d) for i, d in enumerate(body)) % 10 == check


def detect_input_type(raw: str) -> str:
    s = raw.strip()
    if CAS_RE.match(s):
        return "cas"
    # Most chemical names are not valid SMILES (e.g. "Topiramate" fails to parse),
    # so a successful RDKit parse is a good signal. Use the explicit input_type to override.
    if chem.mol_from_smiles(s) is not None:
        return "smiles"
    return "name"


def _get(url: str) -> dict | None:
    settings = get_settings()
    try:
        r = httpx.get(url, timeout=settings.http_timeout_s, headers={"User-Agent": settings.user_agent})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _props_to_compound(p: dict) -> Compound | None:
    smiles = p.get("SMILES") or p.get("IsomericSMILES") or p.get("CanonicalSMILES") or p.get("ConnectivitySMILES")
    if not smiles:
        return None
    local = chem.describe(smiles) or {}
    return Compound(
        inchikey=p.get("InChIKey") or local.get("inchikey"),
        smiles=local.get("smiles", smiles),
        name=p.get("Title") or p.get("IUPACName"),
        formula=p.get("MolecularFormula") or local.get("formula"),
        mol_weight=float(p["MolecularWeight"]) if p.get("MolecularWeight") else local.get("mol_weight"),
        pubchem_cid=p.get("CID"),
    )


def _pubchem_cas(cid: int) -> str | None:
    data = _get(f"{PUBCHEM}/compound/cid/{cid}/synonyms/JSON")
    if not data:
        return None
    try:
        synonyms = data["InformationList"]["Information"][0]["Synonym"]
    except (KeyError, IndexError):
        return None
    for syn in synonyms:
        if is_valid_cas(syn):
            return syn
    return None


def _pubchem_lookup(namespace: str, term: str) -> list[Compound]:
    data = _get(f"{PUBCHEM}/compound/{namespace}/{quote(term, safe='')}/property/{_PROPS}/JSON")
    if not data:
        return []
    out = []
    for p in data.get("PropertyTable", {}).get("Properties", [])[:5]:
        c = _props_to_compound(p)
        if c:
            out.append(c)
    return out


def _backfill_cas(compound: Compound | None) -> Compound | None:
    if compound is None or compound.cas or not compound.pubchem_cid:
        return compound
    cas = _pubchem_cas(compound.pubchem_cid)
    if cas:
        compound.cas = cas
        repository.upsert_compound(compound)
    return compound


def resolve(raw: str, input_type: str = "auto") -> ResolveResult:
    raw = (raw or "").strip()
    if not raw:
        return ResolveResult(error="Enter a structure, SMILES, name or CAS number.")
    kind = detect_input_type(raw) if input_type == "auto" else input_type

    if kind == "smiles":
        info = chem.describe(raw)
        if not info:
            return ResolveResult(error=f"RDKit could not parse the SMILES '{raw}'.")
        cached = repository.get_compound(info["inchikey"])
        if cached:
            return ResolveResult(compound=_backfill_cas(cached))
        hits = _pubchem_lookup("inchikey", info["inchikey"])
        compound = hits[0] if hits else Compound(**info)
        compound.smiles = info["smiles"]
        if compound.pubchem_cid and not compound.cas:
            compound.cas = _pubchem_cas(compound.pubchem_cid)
        repository.upsert_compound(compound)
        return ResolveResult(compound=compound)

    # name or CAS
    cached = repository.find_compound_local(raw)
    if cached:
        return ResolveResult(compound=_backfill_cas(cached))

    hits = _pubchem_lookup("name", raw)
    if not hits:
        return ResolveResult(
            error=f"No compound found for '{raw}'. Check the spelling, or draw the structure instead."
        )
    # PubChem can return several CIDs for one name (salts, stereoisomers).
    unique = {h.inchikey: h for h in hits}
    hits = list(unique.values())
    for h in hits:
        if h.pubchem_cid and not h.cas:
            h.cas = raw if kind == "cas" and is_valid_cas(raw) else _pubchem_cas(h.pubchem_cid)
    if len(hits) > 1:
        return ResolveResult(candidates=hits)

    compound = hits[0]
    repository.upsert_compound(compound, synonyms=[raw])
    return ResolveResult(compound=_backfill_cas(compound))
