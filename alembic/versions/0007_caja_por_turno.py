"""Un monto inicial por método en la caja.

Revision ID: 0007_caja_por_turno
Revises: 0006_caja_unica
Create Date: 2026-11-26

Dos toques seguidos en «Abrir caja» guardaban los montos iniciales dos veces.
Se deja uno por (caja, método) y se crea el índice único.
Idempotente como las anteriores.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007_caja_por_turno"
down_revision: Union[str, None] = "0006_caja_unica"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM caja_montos_iniciales m
        USING (
            SELECT id, row_number() OVER (PARTITION BY caja_id, metodo ORDER BY id) AS n
            FROM caja_montos_iniciales
        ) d
        WHERE m.id = d.id AND d.n > 1
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_caja_monto_metodo "
        "ON caja_montos_iniciales (caja_id, metodo)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_caja_monto_metodo")
