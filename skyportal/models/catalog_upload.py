"""Internal staging tables for catalog uploads."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from baselayer.app.models import Base

catalog_uploads = sa.Table(
    "catalog_uploads",
    Base.metadata,
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

catalog_upload_chunks = sa.Table(
    "catalog_upload_chunks",
    Base.metadata,
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
