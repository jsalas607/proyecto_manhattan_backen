"""Elimina la columna `tipo` de productos (ya no se usa).

Revision ID: 0002_drop_producto_tipo
Revises: 0001_initial
Create Date: 2026-06-20

Usa DROP/ADD COLUMN IF [NOT] EXISTS para ser idempotente: la baseline
`0001_initial` hace `create_all` desde los modelos, por lo que una BD nueva
ya no tendrá la columna, mientras que una BD existente sí la tiene.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_drop_producto_tipo"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE productos DROP COLUMN IF EXISTS tipo")


def downgrade() -> None:
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS tipo VARCHAR DEFAULT 'plato'")
