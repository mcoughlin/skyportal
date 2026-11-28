"""Support point catalog releases and catalog-scoped footprint names."""

import healpix_alchemy as ha
import sqlalchemy as sa

from alembic import op

revision = "8f64aa810ed2"
down_revision = "964a3d287b51"
branch_labels = None
depends_on = None


def base_columns():
    return (
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=False),
    )


def upgrade():
    op.add_column(
        "spatial_catalogs",
        sa.Column("kind", sa.String(), nullable=False, server_default="footprint"),
    )
    op.add_column("spatial_catalogs", sa.Column("url", sa.String()))

    entries = "spatial_catalog_entries"
    tiles = "spatial_catalog_entriess"
    op.add_column(tiles, sa.Column("catalog_id", sa.Integer()))
    op.execute(
        f"""
        UPDATE {tiles} AS tile SET catalog_id = entry.catalog_id
        FROM {entries} AS entry WHERE tile.entry_name = entry.entry_name
        """
    )
    op.alter_column(tiles, "catalog_id", nullable=False)
    op.create_unique_constraint(
        "uq_spatial_catalog_entries_name", entries, ["catalog_id", "entry_name"]
    )
    op.create_foreign_key(
        "fk_spatial_catalog_tiles_entry",
        tiles,
        entries,
        ["catalog_id", "entry_name"],
        ["catalog_id", "entry_name"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "spatial_catalog_entriess_entry_name_fkey", tiles, type_="foreignkey"
    )
    op.drop_index("ix_spatial_catalog_entries_entry_name", table_name=entries)
    op.create_index(
        "ix_spatial_catalog_tiles_entry", tiles, ["catalog_id", "entry_name"]
    )

    op.create_table(
        "catalog_point_releases",
        *base_columns(),
        sa.Column(
            "catalog_id",
            sa.Integer(),
            sa.ForeignKey("spatial_catalogs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("entries_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("catalog_id", "version"),
    )
    op.create_index(
        "ix_catalog_point_releases_active",
        "catalog_point_releases",
        ["catalog_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "catalog_points",
        *base_columns(),
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey("catalog_point_releases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("ra", sa.Float()),
        sa.Column("dec", sa.Float()),
        sa.Column("healpix", ha.Point()),
        sa.Column("object_type", sa.String()),
        sa.Column("redshift", sa.Float()),
        sa.Column("coordinate_bibcode", sa.String()),
        sa.UniqueConstraint("release_id", "external_id"),
    )
    op.create_index("ix_catalog_points_healpix", "catalog_points", ["healpix"])
    op.execute(
        "CREATE INDEX ix_catalog_points_point ON catalog_points "
        '((cosd(ra) * cosd("dec")), (sind(ra) * cosd("dec")), sind("dec"))'
    )

    op.create_table(
        "catalog_identifiers",
        *base_columns(),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["release_id", "external_id"],
            ["catalog_points.release_id", "catalog_points.external_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("release_id", "name", "external_id"),
    )
    op.create_index(
        "ix_catalog_identifiers_point",
        "catalog_identifiers",
        ["release_id", "external_id"],
    )
    op.execute(
        "CREATE INDEX ix_catalog_identifiers_lookup ON catalog_identifiers "
        "(lower(regexp_replace(name, '[[:space:]]+', '', 'g')), release_id)"
    )
    op.create_index(
        "ix_catalog_point_releases_created_at", "catalog_point_releases", ["created_at"]
    )


def downgrade():
    entries = "spatial_catalog_entries"
    tiles = "spatial_catalog_entriess"
    # Reinstating the unique index first fails safely if newer catalogs reuse a name.
    op.create_index(
        "ix_spatial_catalog_entries_entry_name", entries, ["entry_name"], unique=True
    )
    op.create_foreign_key(
        "spatial_catalog_entriess_entry_name_fkey",
        tiles,
        entries,
        ["entry_name"],
        ["entry_name"],
        ondelete="CASCADE",
    )
    op.drop_constraint("fk_spatial_catalog_tiles_entry", tiles, type_="foreignkey")
    op.drop_index("ix_spatial_catalog_tiles_entry", table_name=tiles)
    op.drop_column(tiles, "catalog_id")
    op.drop_constraint("uq_spatial_catalog_entries_name", entries, type_="unique")

    for table in ("catalog_identifiers", "catalog_points", "catalog_point_releases"):
        op.drop_table(table)
    op.execute("DELETE FROM spatial_catalogs WHERE kind = 'point'")
    op.drop_column("spatial_catalogs", "url")
    op.drop_column("spatial_catalogs", "kind")
