"""Add recommendation supersession metadata.

Revision ID: e74b2c19a6f1
Revises: 51a4c34d1f2b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e74b2c19a6f1"
down_revision: Union[str, Sequence[str], None] = "51a4c34d1f2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_recommendations",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "purchase_recommendations",
        sa.Column("superseded_by_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "purchase_recommendations",
        sa.Column("supersession_reason", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_purchase_recommendations_superseded_by_id",
        "purchase_recommendations",
        "purchase_recommendations",
        ["superseded_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_purchase_recommendations_superseded_by_id",
        "purchase_recommendations",
        ["superseded_by_id"],
    )


def downgrade() -> None:
    has_supersession_history = op.get_bind().execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM purchase_recommendations
                WHERE superseded_at IS NOT NULL
                   OR superseded_by_id IS NOT NULL
                   OR supersession_reason IS NOT NULL
            )
            """
        )
    ).scalar()
    if has_supersession_history:
        raise RuntimeError(
            "Cannot remove recommendation supersession metadata while "
            "supersession history exists."
        )

    op.drop_index(
        "ix_purchase_recommendations_superseded_by_id",
        table_name="purchase_recommendations",
    )
    op.drop_constraint(
        "fk_purchase_recommendations_superseded_by_id",
        "purchase_recommendations",
        type_="foreignkey",
    )
    op.drop_column("purchase_recommendations", "supersession_reason")
    op.drop_column("purchase_recommendations", "superseded_by_id")
    op.drop_column("purchase_recommendations", "superseded_at")
