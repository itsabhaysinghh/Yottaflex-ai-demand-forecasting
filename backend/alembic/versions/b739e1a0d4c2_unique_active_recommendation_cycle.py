"""Enforce one active recommendation per SKU/store/date cycle.

Revision ID: b739e1a0d4c2
Revises: e74b2c19a6f1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b739e1a0d4c2"
down_revision: Union[str, Sequence[str], None] = "e74b2c19a6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    duplicate_cycle = op.get_bind().execute(
        sa.text(
            """
            SELECT sku_id, store_id, recommendation_date
            FROM purchase_recommendations
            WHERE superseded_at IS NULL
            GROUP BY sku_id, store_id, recommendation_date
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate_cycle is not None:
        raise RuntimeError(
            "Cannot enforce recommendation-cycle uniqueness while active "
            "duplicates exist. Review and explicitly supersede duplicate "
            "records before retrying this migration."
        )

    op.create_index(
        "uq_purchase_recommendations_current_cycle",
        "purchase_recommendations",
        ["sku_id", "store_id", "recommendation_date"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_purchase_recommendations_current_cycle",
        table_name="purchase_recommendations",
    )
