"""Read-only database access for the live sanctions data + crypto exposure index.

`screensmart_app` does NOT import the sibling services (`sanctions_ingestion`,
`exposure_graph`) — they both happen to use the package name `screensmart`, which would
collide. Instead we read their shared Postgres tables directly with SQLAlchemy Core:

  * `opensanctions_target` — the consolidated entity list (populated by sanctions_ingestion)
  * `crypto_wallet`        — sanctioned wallet addresses
  * `exposure_index`       — precomputed crypto graph-hop exposure (populated by exposure_graph)

sqlalchemy/psycopg are only imported here, so the parquet-only path never needs them.
"""
from __future__ import annotations
import functools
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .domain.models import SanctionedEntity
from .domain.enums import EntitySchema

DEFAULT_DB_URL = "postgresql+psycopg://screensmart:screensmart@localhost:5432/screensmart"


@functools.lru_cache(maxsize=4)
def get_engine(url: str = DEFAULT_DB_URL) -> Engine:
    """Cached read-only engine (pool_pre_ping survives idle DB connections)."""
    return create_engine(url, future=True, pool_pre_ping=True)


def _lst(v) -> list[str]:
    """Postgres ARRAY columns come back as lists already; be defensive about NULLs."""
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if x is not None and str(x).strip()]
    return [s.strip() for s in str(v).split(";") if s.strip()]


def load_entities(engine: Engine, dataset: str = "sanctions") -> list[SanctionedEntity]:
    """Load consolidated entities from `opensanctions_target` for one dataset feed."""
    sql = text(
        "SELECT entity_id, schema, name, aliases, birth_date, countries, "
        "       identifiers, sanctions, first_seen "
        "FROM opensanctions_target WHERE dataset = :ds AND name IS NOT NULL"
    )
    out: list[SanctionedEntity] = []
    with engine.connect() as conn:
        for i, r in enumerate(conn.execute(sql, {"ds": dataset}).mappings()):
            out.append(SanctionedEntity(
                id=r["entity_id"] or f"{dataset}-{i}",
                schema=EntitySchema.coerce(r["schema"] or "Other"),
                name=r["name"],
                aliases=_lst(r["aliases"]),
                countries=_lst(r["countries"]),
                programs=_lst(r["sanctions"]),
                dob=(r["birth_date"] or None),
                identifiers=_lst(r["identifiers"]),
                first_seen=(r["first_seen"] or None),
            ))
    return out


def load_wallet_entities(engine: Engine) -> list[SanctionedEntity]:
    """Load sanctioned wallets from `crypto_wallet` as CryptoWallet entities so the index's
    existing wallet-set logic picks them up (entity name == address)."""
    sql = text("SELECT DISTINCT address, entity_ref, entity_name FROM crypto_wallet "
               "WHERE address IS NOT NULL")
    out: list[SanctionedEntity] = []
    with engine.connect() as conn:
        for r in conn.execute(sql).mappings():
            addr = r["address"]
            out.append(SanctionedEntity(
                id=r["entity_ref"] or addr,
                schema=EntitySchema.CRYPTO_WALLET,
                name=addr,
                aliases=[], countries=[],
                programs=([r["entity_name"]] if r["entity_name"] else []),
            ))
    return out


def lookup_exposure(engine: Engine, address: str) -> Optional[dict]:
    """Look up precomputed crypto graph-hop exposure for an address (node_key).
    Returns {exposure_score, best_depth, best_path, source_risk_node, reason} or None."""
    sql = text(
        "SELECT exposure_score, best_depth, best_path, source_risk_node, reason "
        "FROM exposure_index WHERE node_key = :k"
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"k": address}).mappings().first()
    if row is None:
        return None
    return {
        "exposure_score": float(row["exposure_score"]),
        "best_depth": row["best_depth"],
        "best_path": row["best_path"],
        "source_risk_node": row["source_risk_node"],
        "reason": row["reason"],
    }
