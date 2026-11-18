"""Venta al detalle: código de barras, costo y stock en productos; precio y
costo congelados en cada ítem vendido; kárdex `stock_movimientos`.

Revision ID: 0005_stock_retail
Revises: 0004_user_is_active
Create Date: 2026-11-17

Idempotente como las anteriores: la baseline `0001_initial` hace `create_all`
desde los modelos, así que en una BD nueva todo esto ya existe.
Los productos existentes quedan con `controla_stock = false` (los platos de
restaurante siguen igual).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_stock_retail"
down_revision: Union[str, None] = "0004_user_is_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in (
        "codigo_barras VARCHAR",
        "costo DOUBLE PRECISION NOT NULL DEFAULT 0",
        "controla_stock BOOLEAN NOT NULL DEFAULT false",
        "stock DOUBLE PRECISION NOT NULL DEFAULT 0",
        "stock_minimo DOUBLE PRECISION NOT NULL DEFAULT 0",
        "unidad VARCHAR NOT NULL DEFAULT 'und'",
    ):
        op.execute(f"ALTER TABLE productos ADD COLUMN IF NOT EXISTS {col}")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_producto_codigo_barras "
        "ON productos (restaurant_id, codigo_barras)"
    )
    for col in ("precio_unitario DOUBLE PRECISION", "costo_unitario DOUBLE PRECISION"):
        op.execute(f"ALTER TABLE venta_items ADD COLUMN IF NOT EXISTS {col}")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_movimientos (
            id VARCHAR PRIMARY KEY,
            restaurant_id VARCHAR NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
            producto_id VARCHAR NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
            tipo VARCHAR NOT NULL,
            cantidad DOUBLE PRECISION NOT NULL,
            stock_resultante DOUBLE PRECISION NOT NULL,
            costo_unitario DOUBLE PRECISION NOT NULL,
            motivo VARCHAR NOT NULL,
            nota VARCHAR NOT NULL,
            venta_id VARCHAR REFERENCES ventas(id) ON DELETE SET NULL,
            usuario_id VARCHAR REFERENCES users(id) ON DELETE SET NULL,
            fecha TIMESTAMP WITH TIME ZONE NOT NULL
        )
        """
    )
    for col in ("restaurant_id", "producto_id", "venta_id", "fecha"):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_stock_movimientos_{col} ON stock_movimientos ({col})"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stock_movimientos")
    op.execute("ALTER TABLE venta_items DROP COLUMN IF EXISTS costo_unitario")
    op.execute("ALTER TABLE venta_items DROP COLUMN IF EXISTS precio_unitario")
    op.execute("DROP INDEX IF EXISTS uq_producto_codigo_barras")
    for col in ("unidad", "stock_minimo", "stock", "controla_stock", "costo", "codigo_barras"):
        op.execute(f"ALTER TABLE productos DROP COLUMN IF EXISTS {col}")
