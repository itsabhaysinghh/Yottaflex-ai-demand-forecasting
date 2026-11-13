"""Allow undefined WAPE for evaluations with zero actual demand.

Revision ID: 51a4c34d1f2b
Revises: 90467569fec7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "51a4c34d1f2b"
down_revision: Union[str, Sequence[str], None] = "90467569fec7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "forecast_evaluations",
        "wape",
        existing_type=sa.Numeric(precision=6, scale=4),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM forecast_evaluations WHERE wape IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot make forecast_evaluations.wape non-null while undefined WAPE records exist';
            END IF;
        END
        $$;
        """
    )
    op.alter_column(
        "forecast_evaluations",
        "wape",
        existing_type=sa.Numeric(precision=6, scale=4),
        nullable=False,
    )
