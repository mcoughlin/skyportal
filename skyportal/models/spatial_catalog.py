__all__ = [
    "SpatialCatalog",
    "SpatialCatalogEntry",
    "SpatialCatalogEntryTile",
    "CatalogPoint",
    "CatalogPointRelease",
    "CatalogIdentifier",
]

import conesearch_alchemy as ca
import healpix_alchemy
import healpy
import ligo.skymap.bayestar as ligo_bayestar
import numpy as np
import sqlalchemy as sa
from astropy.table import Table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declared_attr, deferred, relationship

from baselayer.app.models import (
    AccessibleIfRelatedRowsAreAccessible,
    Base,
    CustomUserAccessControl,
)

from .group import groups_members_access_logic


class SpatialCatalog(Base):
    """Spatial catalog information, composed of SpatialCatalogEntry's"""

    __tablename__ = "spatial_catalogs"

    read = CustomUserAccessControl(groups_members_access_logic)

    groups = relationship(
        "Group",
        secondary="group_spatialcatalogs",
        cascade="save-update, merge, refresh-expire, expunge",
        passive_deletes=True,
        doc=(
            "Groups that can see this catalog. A public catalog is attached to "
            "the sitewide public group; a proprietary one only to the groups "
            "entitled to it."
        ),
    )

    catalog_name = sa.Column(
        sa.String, unique=True, nullable=False, doc="Name of the catalog.", index=True
    )

    kind = sa.Column(sa.String, nullable=False, server_default="footprint")
    url = sa.Column(sa.String)

    entries = relationship(
        "SpatialCatalogEntry",
        cascade="save-update, merge, refresh-expire, expunge, delete",
        passive_deletes=True,
        order_by="SpatialCatalogEntry.entry_name",
        doc="Entries associated with this catalog.",
    )


class SpatialCatalogEntry(Base):
    """Spatial catalog entry"""

    __tablename__ = "spatial_catalog_entries"

    read = AccessibleIfRelatedRowsAreAccessible(catalog="read")

    catalog_id = sa.Column(
        sa.ForeignKey("spatial_catalogs.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="localization ID",
    )

    catalog = relationship(
        "SpatialCatalog",
        foreign_keys=catalog_id,
        back_populates="entries",
        doc="The SpatialCatalog that saved this SpatialCatalogEntry belongs to",
    )

    entry_name = sa.Column(sa.String, nullable=False, doc="Entry name")

    data = sa.Column(
        JSONB,
        doc="Entry initialization properties in JSON format.",
        nullable=False,
        index=True,
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "catalog_id", "entry_name", name="uq_spatial_catalog_entries_name"
        ),
    )

    nside = 512
    # HEALPix resolution used for flat (non-multiresolution) operations.

    uniq = deferred(
        sa.Column(
            sa.ARRAY(sa.BigInteger),
            nullable=False,
            doc="Multiresolution HEALPix UNIQ pixel index array",
        )
    )

    probdensity = deferred(
        sa.Column(
            sa.ARRAY(sa.Float),
            nullable=False,
            doc="Multiresolution HEALPix probability density array",
        )
    )

    @property
    def table(self):
        """Get multiresolution HEALPix dataset, probability density only."""
        return Table(
            [np.asarray(self.uniq, dtype=np.int64), self.probdensity],
            names=["UNIQ", "PROBDENSITY"],
        )

    @property
    def flat(self):
        """Get flat resolution HEALPix dataset, probability density only."""
        order = healpy.nside2order(SpatialCatalogEntry.nside)
        result = ligo_bayestar.rasterize(self.table, order)["PROB"]
        return healpy.reorder(result, "NESTED", "RING")


class SpatialCatalogEntryTile(Base):
    """This is a single tile within a catalog entry (as in the SpatialCatalogEntry table).
    Each tile has an associated healpix id and probability density."""

    __tablename__ = "spatial_catalog_entriess"

    catalog_id = sa.Column(sa.Integer, nullable=False)
    entry_name = sa.Column(sa.String, nullable=False)

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["catalog_id", "entry_name"],
            [
                "spatial_catalog_entries.catalog_id",
                "spatial_catalog_entries.entry_name",
            ],
            ondelete="CASCADE",
            name="fk_spatial_catalog_tiles_entry",
        ),
        sa.Index("ix_spatial_catalog_tiles_entry", "catalog_id", "entry_name"),
    )

    probdensity = sa.Column(
        sa.Float,
        nullable=False,
        index=True,
        doc="Probability density for the tile",
    )

    healpix = sa.Column(healpix_alchemy.Tile, primary_key=True, index=True)


class CatalogPointRelease(Base):
    """A loaded version of a point catalog."""

    __tablename__ = "catalog_point_releases"
    __table_args__ = (
        sa.UniqueConstraint("catalog_id", "version"),
        sa.Index(
            "ix_catalog_point_releases_active",
            "catalog_id",
            unique=True,
            postgresql_where=sa.text("active"),
        ),
    )

    read = AccessibleIfRelatedRowsAreAccessible(catalog="read")

    catalog_id = sa.Column(
        sa.ForeignKey("spatial_catalogs.id", ondelete="CASCADE"), nullable=False
    )
    catalog = relationship("SpatialCatalog")
    version = sa.Column(sa.String, nullable=False)
    active = sa.Column(sa.Boolean, nullable=False, server_default=sa.false())
    entries_count = sa.Column(sa.BigInteger, nullable=False, server_default="0")


class CatalogPoint(Base, ca.Point):
    """An entry in a catalog release, optionally with an indexed sky position."""

    __tablename__ = "catalog_points"
    index_created_at = False

    @declared_attr
    def __table_args__(cls):
        *args, kwargs = super().__table_args__
        return (*args, sa.UniqueConstraint("release_id", "external_id"), kwargs)

    read = AccessibleIfRelatedRowsAreAccessible(release="read")

    release_id = sa.Column(
        sa.ForeignKey("catalog_point_releases.id", ondelete="CASCADE"), nullable=False
    )
    release = relationship("CatalogPointRelease")
    external_id = sa.Column(sa.String, nullable=False)
    name = sa.Column(sa.String, nullable=False)
    healpix = sa.Column(healpix_alchemy.Point, index=True)
    object_type = sa.Column(sa.String)
    redshift = sa.Column(sa.Float)
    coordinate_bibcode = sa.Column(sa.String)


def catalog_lookup_name(value):
    return sa.func.lower(
        sa.func.regexp_replace(
            value,
            sa.literal_column("'[[:space:]]+'"),
            sa.literal_column("''"),
            sa.literal_column("'g'"),
        )
    )


class CatalogIdentifier(Base):
    """An identifier attached to one point entry in the same release."""

    __tablename__ = "catalog_identifiers"
    index_created_at = False
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["release_id", "external_id"],
            ["catalog_points.release_id", "catalog_points.external_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("release_id", "name", "external_id"),
        sa.Index("ix_catalog_identifiers_point", "release_id", "external_id"),
    )

    read = AccessibleIfRelatedRowsAreAccessible(point="read")
    point = relationship("CatalogPoint")

    release_id = sa.Column(sa.Integer, nullable=False)
    external_id = sa.Column(sa.String, nullable=False)
    name = sa.Column(sa.String, nullable=False)


sa.Index(
    "ix_catalog_identifiers_lookup",
    catalog_lookup_name(CatalogIdentifier.name),
    CatalogIdentifier.release_id,
)
