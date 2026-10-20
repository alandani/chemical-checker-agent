"""Database schema and session handling (SQLite for local dev, PostgreSQL in Docker)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from typing import Iterator

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from core.config import DATA_DIR, get_settings
from core.models import utcnow


class Base(DeclarativeBase):
    pass


class CompoundRow(Base):
    __tablename__ = "compounds"

    inchikey: Mapped[str] = mapped_column(String(27), primary_key=True)
    smiles: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    cas: Mapped[str | None] = mapped_column(String(32), index=True)
    formula: Mapped[str | None] = mapped_column(String(64))
    mol_weight: Mapped[float | None] = mapped_column(Float)
    pubchem_cid: Mapped[int | None] = mapped_column(Integer)
    synonyms: Mapped[list | None] = mapped_column(JSON)


class VendorRow(Base):
    __tablename__ = "vendors"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(64))
    base_url: Mapped[str] = mapped_column(Text)
    last_scrape_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scrape_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_error: Mapped[str | None] = mapped_column(Text)
    scrape_attempts: Mapped[int] = mapped_column(Integer, default=0)
    scrape_successes: Mapped[int] = mapped_column(Integer, default=0)


class OfferRow(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    compound_inchikey: Mapped[str] = mapped_column(ForeignKey("compounds.inchikey"), index=True)
    vendor: Mapped[str] = mapped_column(String(128), index=True)
    pack_qty: Mapped[float | None] = mapped_column(Float)
    pack_unit: Mapped[str | None] = mapped_column(String(16))
    pack_grams: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(8))
    price_aud: Mapped[float | None] = mapped_column(Float)
    price_aud_per_g: Mapped[float | None] = mapped_column(Float)
    purity: Mapped[float | None] = mapped_column(Float)
    url: Mapped[str | None] = mapped_column(Text)
    in_stock: Mapped[bool | None] = mapped_column(Boolean)
    quote_only: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReactionRow(Base):
    __tablename__ = "reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_inchikey: Mapped[str] = mapped_column(String(27), index=True)
    product_smiles: Mapped[str] = mapped_column(Text)
    reactants_smiles: Mapped[str] = mapped_column(Text)  # dot-separated
    equivalents: Mapped[list | None] = mapped_column(JSON)
    conditions: Mapped[str | None] = mapped_column(Text)
    yield_: Mapped[float | None] = mapped_column("yield", Float)
    reference: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="uspto")


class RunRow(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    compound_label: Mapped[str | None] = mapped_column(String(255))
    inchikey: Mapped[str | None] = mapped_column(String(27), index=True)
    status: Mapped[str] = mapped_column(String(16))
    fits_budget: Mapped[bool | None] = mapped_column(Boolean)
    best_cost_aud: Mapped[float | None] = mapped_column(Float)
    budget_aud: Mapped[float | None] = mapped_column(Float)
    state_json: Mapped[str] = mapped_column(Text)


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
