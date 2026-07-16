"""users.is_active — desactivar dueños que dejan de pagar (sin borrar datos).

Revision ID: 0004_user_is_active
Revises: 0003_owner_isolation
Create Date: 2026-07-16

Idempotente (ADD COLUMN IF NOT EXISTS): la baseline `0001_initial` hace
`create_all` desde los modelos, así que una BD nueva ya tendrá la columna.
Los usuarios existentes quedan activos (DEFAULT true).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_user_is_active"
down_revision: Union[str, None] = "0003_owner_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active")
