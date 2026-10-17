"""pulse meals : estimation depuis la photo du repas (doc 37 §5.3)

Ajoute la confiance de l'estimation, l'origine des macros et l'empreinte de la photo
(la photo elle-même n'est jamais conservée).

Revision ID: 20261017_0057
Revises: 20261017_0056
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0057"
down_revision: str | None = "20261017_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pulse_meals", sa.Column("confidence", sa.Numeric(4, 3), nullable=True))
    op.add_column("pulse_meals", sa.Column("macros_estimated", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("pulse_meals", sa.Column("photo_sha256", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pulse_meals", "photo_sha256")
    op.drop_column("pulse_meals", "macros_estimated")
    op.drop_column("pulse_meals", "confidence")
