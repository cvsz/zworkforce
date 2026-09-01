"""initial persistence tables for audit events and paper orders

Revision ID: 20260524_0001
Revises:
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260524_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.String(length=4096), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=32), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("base_amount", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("strategy_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("paper_orders")
    op.drop_table("audit_events")
