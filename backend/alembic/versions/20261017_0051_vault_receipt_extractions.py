"""vault receipt extractions (justificatifs : OCR → brouillon → validation)

Doc 37 §3, doc 59 VAU-04/05 et maquette 05 « Importer un justificatif ». Une photo
de ticket est lue par le service OCR, un brouillon de dépense est proposé, et la
transaction n'est écrite dans le registre qu'après validation par l'utilisateur.
L'image est conservée comme justificatif une fois validée ; annulée, elle est effacée.

Revision ID: 20261017_0051
Revises: 20261017_0050
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0051"
down_revision: str | None = "20261017_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "vault_receipt_extractions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_app", sa.Text(), nullable=False, server_default=sa.text("'vault'")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("storage_pointer", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("draft", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Pas de clé étrangère vers le registre : il reste intouché (trigger append-only du
        # TRUNCATE) ; le lien inverse est external_ref = receipt:{id} sur la transaction.
        sa.Column("transaction_id", UUID, nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("entry_app IN ('vault', 'imperium')", name="entry_app_check"),
        sa.CheckConstraint("status IN ('ready', 'failed', 'validated', 'cancelled')", name="status_check"),
        sa.CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        sa.CheckConstraint("status <> 'validated' OR transaction_id IS NOT NULL", name="validated_has_transaction"),
    )
    op.create_index("vault_receipt_extractions_user_created_idx", "vault_receipt_extractions", ["user_id", "created_at"])
    op.create_index(
        "vault_receipt_extractions_user_idempotency_idx",
        "vault_receipt_extractions",
        ["user_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("vault_receipt_extractions_user_idempotency_idx", table_name="vault_receipt_extractions")
    op.drop_index("vault_receipt_extractions_user_created_idx", table_name="vault_receipt_extractions")
    op.drop_table("vault_receipt_extractions")
