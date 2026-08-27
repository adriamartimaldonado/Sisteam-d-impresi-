"""esquema inicial del central (tablas del §11)

Revision ID: 0001
Revises:
Create Date: 2026-07-29

La migracion inicial crea el esquema a partir de los modelos SQLAlchemy
(`Base.metadata`), de modo que migracion y modelos no puedan desfasarse. Las
migraciones posteriores (Fase 1+) seran deltas granulares.
"""

from __future__ import annotations

from alembic import op

# raiz del repo ya esta en sys.path por env.py
from central.app.modelos import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
