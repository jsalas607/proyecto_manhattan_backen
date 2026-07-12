"""Baseline: crea todas las tablas desde los modelos.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-15

Esta migración baseline crea el esquema completo a partir de Base.metadata.
Las migraciones futuras se generan con `alembic revision --autogenerate` y
diferencian contra este estado.
"""
from typing import Sequence, Union

from alembic import op

from app.core.database import Base
import app.models  # noqa: F401  (puebla Base.metadata)

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
