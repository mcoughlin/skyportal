"""Bulk import a pair of SIMBAD basic and ident CSV exports."""

import csv
import math
from contextlib import nullcontext
from itertools import batched

import numpy as np
import sqlalchemy as sa
from astropy import units as u
from healpix_alchemy.constants import HPX

from ..models import (
    CatalogIdentifier,
    CatalogPoint,
    CatalogPointRelease,
    SpatialCatalog,
)
from .catalog_groups import groups_for_ids
from .naive_datetime import utcnow_naive

SIMBAD_URL = "https://simbad.cds.unistra.fr/simbad/"


def csv_rows(source, required):
    path = (
        getattr(source, "name", "uploaded CSV") if hasattr(source, "read") else source
    )
    context = (
        nullcontext(source)
        if hasattr(source, "read")
        else open(source, encoding="utf-8-sig", newline="")
    )
    with context as stream:
        reader = csv.DictReader(stream)
        missing = set(required).difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(sorted(missing))}")
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f"{path}: malformed row at line {reader.line_num}")
            yield {key: value.strip() for key, value in row.items()}


def point_rows(path, release_id, now):
    for batch in batched(csv_rows(path, ("oid", "main_id", "ra", "dec")), 10_000):
        positions = []
        pixels = {}
        records = []
        for index, row in enumerate(batch):
            ra, dec = (float(row[key]) if row[key] else None for key in ("ra", "dec"))
            if ra is not None or dec is not None:
                if not (
                    ra is not None
                    and dec is not None
                    and 0 <= ra < 360
                    and -90 <= dec <= 90
                ):
                    raise ValueError(f"Invalid coordinates for SIMBAD oid {row['oid']}")
                positions.append((index, ra, dec))
            redshift = float(row["rvz_redshift"]) if row.get("rvz_redshift") else None
            if not row["main_id"] or (
                redshift is not None and not math.isfinite(redshift)
            ):
                raise ValueError(f"Invalid metadata for SIMBAD oid {row['oid']}")
            records.append(
                (
                    release_id,
                    str(int(row["oid"])),
                    row["main_id"],
                    ra,
                    dec,
                    row.get("otype") or None,
                    redshift,
                    row.get("coo_bibcode") or None,
                    now,
                    now,
                )
            )
        if positions:
            indices, ras, decs = np.asarray(positions).T
            pixels = dict(
                zip(
                    indices.astype(int),
                    HPX.lonlat_to_healpix(ras * u.deg, decs * u.deg),
                )
            )
        for index, record in enumerate(records):
            pixel = pixels.get(index)
            yield (*record, int(pixel) if pixel is not None else None)


def identifier_rows(path, release_id, now):
    for row in csv_rows(path, ("oidref", "id")):
        if not row["id"]:
            raise ValueError("Empty SIMBAD identifier")
        yield release_id, str(int(row["oidref"])), row["id"], now, now


def copy_rows(session, statement, rows):
    count = 0
    with (
        session.connection().connection.cursor() as cursor,
        cursor.copy(statement) as copy,
    ):
        for row in rows:
            copy.write_row(row)
            count += 1
    return count


def import_simbad(
    session, basic, ident, version, *, group_ids=None, allow_existing=True
):
    """Load and activate a release in the caller's transaction.

    Releases are immutable. Reusing a version activates the previously loaded
    release. The transaction lock serializes creation and refresh of the catalog.
    """
    if not version.strip():
        raise ValueError("A SIMBAD release version is required")
    session.execute(
        sa.select(sa.func.pg_advisory_xact_lock(sa.func.hashtext("catalog:SIMBAD")))
    )
    catalog = session.scalar(
        sa.select(SpatialCatalog).where(SpatialCatalog.catalog_name == "SIMBAD")
    )
    if catalog is None:
        catalog = SpatialCatalog(
            catalog_name="SIMBAD",
            kind="point",
            url=SIMBAD_URL,
            groups=groups_for_ids(session, group_ids),
        )
        session.add(catalog)
        session.flush()
    elif catalog.kind != "point":
        raise ValueError("The name SIMBAD is already used by a footprint catalog")
    elif group_ids is not None and set(group_ids) != {
        group.id for group in catalog.groups
    }:
        raise ValueError("SIMBAD refresh must preserve the catalog's groups")

    release = session.scalar(
        sa.select(CatalogPointRelease).where(
            CatalogPointRelease.catalog_id == catalog.id,
            CatalogPointRelease.version == version,
        )
    )
    if release is not None and not allow_existing:
        raise ValueError(f"SIMBAD release {version} already exists")
    if release is None:
        release = CatalogPointRelease(catalog_id=catalog.id, version=version)
        session.add(release)
        session.flush()
        now = utcnow_naive()
        release.entries_count = copy_rows(
            session,
            """COPY catalog_points
            (release_id, external_id, name, ra, dec, object_type, redshift,
             coordinate_bibcode, created_at, modified, healpix) FROM STDIN""",
            point_rows(basic, release.id, now),
        )
        identifiers_count = copy_rows(
            session,
            """COPY catalog_identifiers
            (release_id, external_id, name, created_at, modified) FROM STDIN""",
            identifier_rows(ident, release.id, now),
        )
        if not release.entries_count or not identifiers_count:
            raise ValueError("Both SIMBAD exports must contain data")
        # Canonical names resolve even when omitted from the identifier export.
        session.execute(
            sa.text("""
                INSERT INTO catalog_identifiers
                    (release_id, external_id, name, created_at, modified)
                SELECT release_id, external_id, name, :now, :now
                FROM catalog_points WHERE release_id = :release_id
                ON CONFLICT (release_id, name, external_id) DO NOTHING
            """),
            {"now": now, "release_id": release.id},
        )
    session.execute(
        sa.update(CatalogPointRelease)
        .where(
            CatalogPointRelease.catalog_id == catalog.id,
            CatalogPointRelease.active,
            CatalogPointRelease.id != release.id,
        )
        .values(active=False)
    )
    release.active = True
    session.flush()
    return release
