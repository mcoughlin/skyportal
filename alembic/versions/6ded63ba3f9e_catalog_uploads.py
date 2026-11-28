"""Stage resumable catalog uploads."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "6ded63ba3f9e"
down_revision = "8f64aa810ed2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "catalog_uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="uploading"),
        sa.Column("result", JSONB),
        sa.Column("error", sa.String),
        sa.UniqueConstraint("owner_id", "fingerprint"),
    )
    op.create_table(
        "catalog_upload_chunks",
        sa.Column(
            "upload_id",
            sa.String(36),
            sa.ForeignKey("catalog_uploads.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("file_name", sa.String(12), primary_key=True),
        sa.Column("chunk_index", sa.Integer, primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
    )


def downgrade():
    op.drop_table("catalog_upload_chunks")
    op.drop_table("catalog_uploads")
