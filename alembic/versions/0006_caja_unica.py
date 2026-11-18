"""Una sola caja por restaurante.

Revision ID: 0006_caja_unica
Revises: 0005_stock_retail
Create Date: 2026-11-18

Al abrir Cartera se hacen varias peticiones a la vez y cada una creaba la
caja si no existía: quedaban dos filas y desde ahí la caja fallaba siempre.
Se dejan las cajas duplicadas en una (la abierta si la hay; si no, la más
antigua) y se pone un índice único en `restaurant_id`.

Idempotente como las anteriores.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006_caja_unica"
down_revision: Union[str, None] = "0005_stock_retail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM caja c
        USING (
            SELECT id, row_number() OVER (
                PARTITION BY restaurant_id
                ORDER BY (status = 'abierta') DESC, abierta_en NULLS LAST, id
            ) AS n
            FROM caja
        ) d
        WHERE c.id = d.id AND d.n > 1
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_caja_restaurant_id")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_caja_restaurant ON caja (restaurant_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_caja_restaurant")
    op.execute("CREATE INDEX IF NOT EXISTS ix_caja_restaurant_id ON caja (restaurant_id)")
