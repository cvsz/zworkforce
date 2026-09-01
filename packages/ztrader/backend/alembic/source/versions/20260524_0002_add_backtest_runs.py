"""add backtest run summary persistence

Revision ID: 20260524_0002
Revises: 20260524_0001
Create Date: 2026-05-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260524_0002"
down_revision = "20260524_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("strategy_id", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("candles_seen", sa.Integer(), nullable=False),
        sa.Column("orders_created", sa.Integer(), nullable=False),
        sa.Column("ending_usdt", sa.Float(), nullable=False),
        sa.Column("ending_btc", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("backtest_runs")
