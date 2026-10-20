"""Shared data models passed between pipeline stages, the UI and the database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

StateName = Literal[
    "RESOLVE",
    "CHECK_MARKET",
    "FIND_KNOWN_ROUTE",
    "PREDICT_ROUTE",
    "PRICE_MATERIALS",
    "COST",
    "EXPLAIN",
    "DONE",
    "NEEDS_INPUT",
]

MassUnit = Literal["mg", "g", "kg"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Query(BaseModel):
    """What the researcher asked for."""

    raw_input: str
    input_type: Literal["auto", "smiles", "name", "cas"] = "auto"
    quantity: float = 1.0
    quantity_unit: MassUnit = "g"
    min_purity: float | None = None  # percent, e.g. 95
    budget: float = 1000.0
    currency: str = "AUD"
    regions: list[str] | None = None  # None = all regions
    allow_predicted: bool = True
    compare_synthesis: bool = False  # also cost a route when the compound is buyable
    max_steps: int = 5
    consumables_margin: float = 0.15  # solvents, workup, consumables
    default_step_yield: float = 0.7  # used when a route step has no recorded yield

    @property
    def grams(self) -> float:
        return self.quantity * {"mg": 1e-3, "g": 1.0, "kg": 1e3}[self.quantity_unit]


class Compound(BaseModel):
    inchikey: str
    smiles: str
    name: str | None = None
    cas: str | None = None
    formula: str | None = None
    mol_weight: float | None = None
    pubchem_cid: int | None = None

    @property
    def label(self) -> str:
        return self.name or self.cas or self.smiles


class Offer(BaseModel):
    vendor: str
    compound_inchikey: str
    pack_qty: float | None = None
    pack_unit: str | None = None
    price: float | None = None
    currency: str | None = None
    price_aud: float | None = None  # price of the whole pack in AUD
    price_aud_per_g: float | None = None
    pack_grams: float | None = None
    purity: float | None = None  # percent
    url: str | None = None
    in_stock: bool | None = None
    quote_only: bool = False
    is_demo: bool = False  # sample data, not a real quote
    scraped_at: datetime = Field(default_factory=utcnow)


class Purchase(BaseModel):
    """The cheapest way to buy a given amount from one offer."""

    offer: Offer
    n_packs: int
    total_aud: float


class RouteStep(BaseModel):
    reactants: list[str]  # SMILES of reactants that end up in the product
    product: str  # SMILES
    equivalents: list[float] | None = None  # per reactant, default 1.0 each
    conditions: str | None = None
    yield_: float | None = Field(default=None, alias="yield")
    reference: str | None = None

    model_config = {"populate_by_name": True}

    @property
    def reaction_smiles(self) -> str:
        return ".".join(self.reactants) + ">>" + self.product


class Route(BaseModel):
    source: Literal["known", "predicted"]
    steps: list[RouteStep]  # ordered from first step to final step
    score: float | None = None
    reference: str | None = None
    notes: str | None = None


class MaterialCost(BaseModel):
    smiles: str
    inchikey: str | None = None
    name: str | None = None
    grams_needed: float
    purchase: Purchase | None = None
    is_demo: bool = False

    @property
    def priced(self) -> bool:
        return self.purchase is not None

    @property
    def line_cost_aud(self) -> float | None:
        return self.purchase.total_aud if self.purchase else None


class CostBreakdown(BaseModel):
    budget_aud: float
    buy: Purchase | None = None
    make_materials_aud: float | None = None
    make_total_aud: float | None = None  # materials + consumables margin
    make_complete: bool = True  # False if any starting material is unpriced
    cheapest: Literal["buy", "make"] | None = None
    best_cost_aud: float | None = None
    fits_budget: bool | None = None

    @property
    def gap_aud(self) -> float | None:
        if self.best_cost_aud is None:
            return None
        return self.budget_aud - self.best_cost_aud


class RunState(BaseModel):
    """Everything the pipeline knows about one analysis run."""

    run_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=utcnow)
    status: Literal["running", "needs_input", "done"] = "running"
    current: StateName = "RESOLVE"
    query: Query
    compound: Compound | None = None
    candidates: list[Compound] = []
    offers: list[Offer] = []
    route: Route | None = None
    alternative_routes: list[Route] = []
    materials: list[MaterialCost] = []
    cost: CostBreakdown | None = None
    explanation: str | None = None
    warnings: list[str] = []
    timings: dict[str, float] = {}

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    @property
    def uses_demo_data(self) -> bool:
        return any(o.is_demo for o in self.offers) or any(m.is_demo for m in self.materials)
