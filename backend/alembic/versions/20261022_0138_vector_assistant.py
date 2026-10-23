"""vector: offres lues par l'assistant de prise de course (lot V2-A, 2026-10-22)

`rides_offers.source` accepte `assistant` : offre lue à l'écran par l'assistant de l'appli (capture accordée à chaque
lancement + OCR embarqué, F10 §5-quater ; lire pour conseiller, jamais agir). L'image et le texte brut ne quittent
jamais la tablette ; seuls les champs reconnus (prix, distances, durées, codes postaux) arrivent ici.

Revision ID: 20261022_0138
Revises: 20261022_0137
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0138"
down_revision: str | None = "20261022_0137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("source_check", "rides_offers", type_="check")
    op.create_check_constraint("source_check", "rides_offers", "source IN ('manual', 'ocr', 'assistant')")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM rides_offers WHERE source = 'assistant'")
    op.drop_constraint("source_check", "rides_offers", type_="check")
    op.create_check_constraint("source_check", "rides_offers", "source IN ('manual', 'ocr')")
