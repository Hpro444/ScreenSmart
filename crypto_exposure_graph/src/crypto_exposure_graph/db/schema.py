"""SQLAlchemy Core schema for the synthetic crypto exposure-graph MVP."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = sa.MetaData()


def _uuid_col() -> sa.Column:
    return sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


crypto_graph_nodes = sa.Table(
    "crypto_graph_nodes",
    metadata,
    _uuid_col(),
    sa.Column("node_key", sa.Text, nullable=False, unique=True),
    sa.Column("chain", sa.Text, nullable=False),
    sa.Column("address", sa.Text, nullable=False),
    sa.Column("node_type", sa.Text, nullable=False),
    sa.Column("display_name", sa.Text),
    sa.Column("risk_level", sa.Text, nullable=False, server_default=sa.text("'NONE'")),
    sa.Column("risk_source", sa.Text),
    sa.Column(
        "created_at",
        sa.DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.UniqueConstraint("chain", "address", name="uq_crypto_graph_nodes_chain_address"),
    sa.Index("ix_crypto_graph_nodes_chain", "chain"),
    sa.Index("ix_crypto_graph_nodes_node_type", "node_type"),
    sa.Index("ix_crypto_graph_nodes_risk_level", "risk_level"),
)

crypto_graph_edges = sa.Table(
    "crypto_graph_edges",
    metadata,
    _uuid_col(),
    sa.Column("from_node_key", sa.Text, nullable=False),
    sa.Column("to_node_key", sa.Text, nullable=False),
    sa.Column("edge_type", sa.Text, nullable=False),
    sa.Column("total_usd_value", sa.Numeric(18, 2)),
    sa.Column("transaction_count", sa.Integer),
    sa.Column("first_seen", sa.Date),
    sa.Column("last_seen", sa.Date),
    sa.Column("confidence", sa.Numeric(8, 4)),
    sa.Column(
        "created_at",
        sa.DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Index("ix_crypto_graph_edges_from_node_key", "from_node_key"),
    sa.Index("ix_crypto_graph_edges_to_node_key", "to_node_key"),
    sa.Index("ix_crypto_graph_edges_edge_type", "edge_type"),
)

crypto_synthetic_screenings = sa.Table(
    "crypto_synthetic_screenings",
    metadata,
    _uuid_col(),
    sa.Column("case_id", sa.Text, nullable=False, unique=True),
    sa.Column("scenario_type", sa.Text, nullable=False),
    sa.Column("chain", sa.Text, nullable=False),
    sa.Column("wallet_address", sa.Text, nullable=False),
    sa.Column("asset", sa.Text),
    sa.Column("amount_usd", sa.Numeric(18, 2)),
    sa.Column("expected_verdict", sa.Text, nullable=False),
    sa.Column("ground_truth_reason", sa.Text),
    sa.Column(
        "created_at",
        sa.DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Index("ix_crypto_synthetic_screenings_scenario_type", "scenario_type"),
    sa.Index("ix_crypto_synthetic_screenings_expected_verdict", "expected_verdict"),
)

crypto_exposure_index = sa.Table(
    "crypto_exposure_index",
    metadata,
    sa.Column("node_key", sa.Text, primary_key=True),
    sa.Column("exposure_score", sa.Numeric(10, 4), nullable=False),
    sa.Column("best_depth", sa.Integer),
    sa.Column("best_path", JSONB, nullable=False),
    sa.Column("source_risk_node", sa.Text, nullable=False),
    sa.Column("reason", sa.Text),
    sa.Column(
        "computed_at",
        sa.DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
)

TABLES_IN_ORDER = [
    crypto_graph_nodes,
    crypto_graph_edges,
    crypto_synthetic_screenings,
    crypto_exposure_index,
]
