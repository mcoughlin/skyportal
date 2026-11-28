"""Read API shared by point catalogs and spatial footprints."""

import math
from urllib.parse import urlencode

import conesearch_alchemy as ca
import sqlalchemy as sa
from astropy import units as u
from healpix_alchemy.constants import HPX
from skyportal_py_models.local_catalogs import (
    CatalogCrossmatchQuery,
    CatalogResolveQuery,
    CatalogSearchResponse,
    LocalCatalogListResponse,
)

from baselayer.app.access import auth_or_token

from ...models import (
    CatalogIdentifier,
    CatalogPoint,
    CatalogPointRelease,
    Galaxy,
    GalaxyCatalog,
    SpatialCatalog,
    SpatialCatalogEntry,
    SpatialCatalogEntryTile,
)
from ...models.spatial_catalog import catalog_lookup_name
from ..base import BaseHandler


async def visible_catalogs(session, catalog=None):
    """Adapt the Galaxy registry so the legacy and shared APIs see the same ACL."""
    spatial_query = (
        SpatialCatalog.select(session.user_or_token)
        .outerjoin(
            CatalogPointRelease,
            sa.and_(
                CatalogPointRelease.catalog_id == SpatialCatalog.id,
                CatalogPointRelease.active,
            ),
        )
        .add_columns(
            CatalogPointRelease.id.label("release_id"),
            CatalogPointRelease.version,
            CatalogPointRelease.entries_count,
        )
        .where(
            sa.or_(
                SpatialCatalog.kind == "footprint",
                CatalogPointRelease.id.is_not(None),
            )
        )
    )
    galaxies_query = GalaxyCatalog.select(session.user_or_token)
    if catalog is not None:
        kind, catalog_id = catalog.split(":")
        catalog_id = int(catalog_id)
        if catalog_id > 2**31 - 1:
            raise ValueError("Invalid catalog ID")
        if kind == "spatial":
            spatial_query = spatial_query.where(SpatialCatalog.id == catalog_id)
            galaxies_query = None
        else:
            galaxies_query = galaxies_query.where(GalaxyCatalog.id == catalog_id)
            spatial_query = None
    catalogs = []
    if spatial_query is not None:
        for row in await session.execute(spatial_query):
            record = row[0]
            catalogs.append(
                {
                    "id": f"spatial:{record.id}",
                    "legacy_id": record.id,
                    "name": record.catalog_name,
                    "geometry": record.kind,
                    "url": record.url,
                    "release": row.version,
                    "entries_count": row.entries_count,
                    "release_id": row.release_id,
                }
            )
    if galaxies_query is not None:
        for record in await session.scalars(galaxies_query):
            catalogs.append(
                {
                    "id": f"galaxy:{record.id}",
                    "legacy_id": record.id,
                    "name": record.name,
                    "geometry": "point",
                    "url": record.url,
                    "release": None,
                    "entries_count": None,
                    "release_id": None,
                }
            )
    if catalog is not None and not catalogs:
        raise ValueError("Catalog not found")
    return sorted(catalogs, key=lambda c: (c["name"].casefold(), c["id"]))


def public_catalog(catalog):
    return {key: value for key, value in catalog.items() if key != "release_id"}


def entry(catalog, external_id, name, ra, dec, **fields):
    return {
        "catalog": catalog["id"],
        "catalog_name": catalog["name"],
        "release": catalog["release"],
        "external_id": str(external_id),
        "name": name,
        "ra": ra,
        "dec": dec,
        **fields,
    }


def point_source(catalog):
    if catalog["release_id"] is not None:
        return CatalogPoint, CatalogPoint.release_id == catalog["release_id"]
    return Galaxy, Galaxy.catalog_id == catalog["legacy_id"]


def point_entry(catalog, point, **fields):
    if isinstance(point, CatalogPoint):
        fields.update(
            object_type=point.object_type,
            redshift=point.redshift,
            coordinate_bibcode=point.coordinate_bibcode,
        )
        external_id = point.external_id
        if catalog["name"] == "SIMBAD":
            fields["url"] = f"{catalog['url']}sim-id?{urlencode({'Ident': point.name})}"
    else:
        external_id = point.id
        fields["redshift"] = point.redshift
    return entry(catalog, external_id, point.name, point.ra, point.dec, **fields)


def footprint_entry(catalog, footprint, **fields):
    return entry(
        catalog,
        footprint.id,
        footprint.entry_name,
        footprint.data.get("ra"),
        footprint.data.get("dec"),
        **fields,
    )


async def resolve_entries(session, catalogs, name, limit):
    matches = []
    for catalog in catalogs:
        if catalog["geometry"] == "footprint":
            query = (
                sa.select(SpatialCatalogEntry)
                .where(
                    SpatialCatalogEntry.catalog_id == catalog["legacy_id"],
                    sa.func.lower(SpatialCatalogEntry.entry_name)
                    == name.replace(" ", "-").lower(),
                )
                .order_by(SpatialCatalogEntry.id)
                .limit(limit)
            )
            matches.extend(
                footprint_entry(catalog, row, matched_alias=row.entry_name)
                for row in await session.scalars(query)
            )
            continue

        model, scope = point_source(catalog)
        if model is Galaxy:
            query = (
                sa.select(Galaxy).where(scope, Galaxy.name == name).order_by(Galaxy.id)
            )
            matches.extend(
                point_entry(catalog, row, matched_alias=row.name)
                for row in await session.scalars(query.limit(limit))
            )
            continue

        # Return each object once, even when it has multiple aliases with the
        # same lookup form. Prefer the exact spelling supplied by the caller.
        alias = CatalogIdentifier
        aliases = (
            sa.select(alias.external_id, alias.name)
            .where(
                alias.release_id == catalog["release_id"],
                catalog_lookup_name(alias.name)
                == catalog_lookup_name(sa.literal(name)),
            )
            .distinct(alias.external_id)
            .order_by(alias.external_id, (alias.name == name).desc(), alias.name)
            .limit(limit)
            .subquery()
        )
        query = (
            sa.select(model, aliases.c.name)
            .join(aliases, model.external_id == aliases.c.external_id)
            .where(scope)
            .order_by(model.external_id)
        )
        matches.extend(
            point_entry(catalog, row, matched_alias=matched)
            for row, matched in await session.execute(query)
        )
    return matches[:limit]


def separation_arcsec(model, ra, dec):
    haversine = sa.func.power(sa.func.sind((model.dec - dec) / 2), 2) + sa.func.cosd(
        model.dec
    ) * math.cos(math.radians(dec)) * sa.func.power(
        sa.func.sind((model.ra - ra) / 2), 2
    )
    return 7200 * sa.func.degrees(
        sa.func.asin(sa.func.sqrt(sa.func.least(1.0, haversine)))
    )


async def crossmatch_entries(session, catalogs, ra, dec, radius_arcsec, limit):
    point = ca.Point(ra=ra, dec=dec)
    pixel = int(HPX.lonlat_to_healpix(ra * u.deg, dec * u.deg))
    matches = []
    for catalog in catalogs:
        if catalog["geometry"] == "footprint":
            tile = SpatialCatalogEntryTile
            footprint = SpatialCatalogEntry
            query = (
                sa.select(footprint)
                .where(
                    footprint.catalog_id == catalog["legacy_id"],
                    sa.exists().where(
                        tile.catalog_id == footprint.catalog_id,
                        tile.entry_name == footprint.entry_name,
                        tile.healpix.contains(sa.cast(pixel, sa.BigInteger)),
                    ),
                )
                .order_by(footprint.entry_name, footprint.id)
                .limit(limit)
            )
            matches.extend(
                footprint_entry(catalog, row, match_type="footprint")
                for row in await session.scalars(query)
            )
            continue

        model, scope = point_source(catalog)
        distance = separation_arcsec(model, ra, dec)
        query = (
            sa.select(model, distance)
            .where(
                scope,
                model.within(point, radius_arcsec / 3600),
                distance <= radius_arcsec,
            )
            .order_by(distance, model.id)
            .limit(limit)
        )
        matches.extend(
            point_entry(catalog, row, match_type="point", separation_arcsec=sep)
            for row, sep in await session.execute(query)
        )

    matches.sort(
        key=lambda match: (
            match.get("separation_arcsec", math.inf),
            match["catalog"],
            match["name"],
            match["external_id"],
        )
    )
    return matches[:limit]


class LocalCatalogHandler(BaseHandler):
    @auth_or_token
    async def get(self) -> LocalCatalogListResponse:
        """
        ---
        summary: List accessible local catalogs
        tags:
          - catalogs
        """
        async with self.AsyncSession() as session:
            catalogs = await visible_catalogs(session)
        return self.success(data=[public_catalog(catalog) for catalog in catalogs])


class LocalCatalogResolveHandler(BaseHandler):
    @auth_or_token
    async def get(self, *, query: CatalogResolveQuery = None) -> CatalogSearchResponse:
        """
        ---
        summary: Resolve a name or alias in local catalogs
        tags:
          - catalogs
        """
        query = self.parse_query(CatalogResolveQuery)
        try:
            async with self.AsyncSession() as session:
                catalogs = await visible_catalogs(session, query.catalog)
                matches = await resolve_entries(
                    session, catalogs, query.name, query.limit + 1
                )
        except ValueError as exc:
            return self.error(str(exc))
        return self.success(
            data={
                "matches": matches[: query.limit],
                "truncated": len(matches) > query.limit,
            }
        )


class LocalCatalogCrossmatchHandler(BaseHandler):
    @auth_or_token
    async def get(
        self, *, query: CatalogCrossmatchQuery = None
    ) -> CatalogSearchResponse:
        """
        ---
        summary: Crossmatch a position against local catalogs
        tags:
          - catalogs
        """
        query = self.parse_query(CatalogCrossmatchQuery)
        try:
            async with self.AsyncSession() as session:
                catalogs = await visible_catalogs(session, query.catalog)
                matches = await crossmatch_entries(
                    session,
                    catalogs,
                    query.ra,
                    query.dec,
                    query.radius_arcsec,
                    query.limit + 1,
                )
        except ValueError as exc:
            return self.error(str(exc))
        return self.success(
            data={
                "matches": matches[: query.limit],
                "truncated": len(matches) > query.limit,
            }
        )
