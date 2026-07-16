"""Multi-inquilino por dueño: users.is_superadmin + restaurants.owner_id.

Revision ID: 0003_owner_isolation
Revises: 0002_drop_producto_tipo
Create Date: 2026-07-15

Aísla los restaurantes por dueño. Idempotente (ADD COLUMN IF NOT EXISTS) porque
la baseline `0001_initial` hace `create_all` desde los modelos: una BD nueva ya
tendrá las columnas, una existente no.

Backfill crítico: los admin ya creados (p. ej. el bootstrap del servidor) se
promueven a superadmin, porque hasta ahora `is_admin=True` significaba "ve todo".
Los dueños nuevos se crearán con is_admin=True e is_superadmin=False.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_owner_isolation"
down_revision: Union[str, None] = "0002_drop_producto_tipo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS owner_id VARCHAR")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_restaurants_owner_id ON restaurants (owner_id)"
    )
    # FK con SET NULL (envuelto en DO para que no falle si ya existe)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_restaurants_owner_id_users'
            ) THEN
                ALTER TABLE restaurants
                    ADD CONSTRAINT fk_restaurants_owner_id_users
                    FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    # Promueve los admin existentes a superadmin (antes is_admin=True = ver todo).
    op.execute("UPDATE users SET is_superadmin = true WHERE is_admin = true")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE restaurants DROP CONSTRAINT IF EXISTS fk_restaurants_owner_id_users"
    )
    op.execute("DROP INDEX IF EXISTS ix_restaurants_owner_id")
    op.execute("ALTER TABLE restaurants DROP COLUMN IF EXISTS owner_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_superadmin")
