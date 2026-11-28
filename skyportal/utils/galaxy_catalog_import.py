"""Load prepared Galaxy rows using the database bulk-copy path."""

import pandas as pd
import sqlalchemy as sa
from astropy import units as u
from healpix_alchemy.constants import HPX

from ..models import GalaxyCatalog
from .catalog_groups import groups_for_ids
from .naive_datetime import utcnow_naive

REQUIRED_COLUMNS = ("name", "ra", "dec")
TEXT_COLUMNS = ("name", "alt_name")
DATA_COLUMNS = (
    *REQUIRED_COLUMNS,
    "alt_name",
    "distmpc",
    "distmpc_unc",
    "redshift",
    "redshift_error",
    "sfr_fuv",
    "sfr_w4",
    "mstar",
    "magb",
    "magk",
    "mag_fuv",
    "mag_nuv",
    "mag_w1",
    "mag_w2",
    "mag_w3",
    "mag_w4",
    "a",
    "b2a",
    "pa",
    "btc",
)
COPY_COLUMNS = (*DATA_COLUMNS, "catalog_id", "healpix", "created_at", "modified")


def import_galaxies(session, path, catalog_name, *, group_ids=None):
    """Append a prepared CSV in chunks and leave the commit to the caller."""
    if not catalog_name.strip():
        raise ValueError("A Galaxy catalog name is required")
    session.execute(
        sa.select(
            sa.func.pg_advisory_xact_lock(sa.func.hashtext(f"galaxy:{catalog_name}"))
        )
    )
    catalog = session.scalar(
        sa.select(GalaxyCatalog).where(GalaxyCatalog.name == catalog_name)
    )
    if catalog is None:
        catalog = GalaxyCatalog(
            name=catalog_name, groups=groups_for_ids(session, group_ids)
        )
        session.add(catalog)
        session.flush()
    elif group_ids is not None and set(group_ids) != {
        group.id for group in catalog.groups
    }:
        raise ValueError("Import must preserve the existing Galaxy catalog's groups")

    now = utcnow_naive()
    quoted = ", ".join(f'"{column}"' for column in COPY_COLUMNS)
    statement = f"COPY galaxys ({quoted}) FROM STDIN WITH (FORMAT csv)"
    dtypes = {key: "string" if key in TEXT_COLUMNS else float for key in DATA_COLUMNS}
    count = 0
    skipped = 0
    blueshifted = 0
    with pd.read_csv(
        path,
        chunksize=100_000,
        usecols=lambda name: name in DATA_COLUMNS,
        dtype=dtypes,
        keep_default_na=False,
        na_values=[""],
    ) as chunks:
        with (
            session.connection().connection.cursor() as cursor,
            cursor.copy(statement) as copy,
        ):
            for chunk in chunks:
                missing = set(REQUIRED_COLUMNS) - set(chunk.columns)
                if missing:
                    raise ValueError(
                        f"Missing Galaxy columns: {', '.join(sorted(missing))}"
                    )
                names = chunk["name"].str.strip()
                valid = (
                    names.notna()
                    & (names != "")
                    & chunk["ra"].ge(0)
                    & chunk["ra"].lt(360)
                    & chunk["dec"].between(-90, 90)
                )
                for key in ("distmpc", "distmpc_unc", "redshift_error"):
                    if key in chunk:
                        valid &= ~chunk[key].lt(0)
                rows = chunk.loc[valid].reindex(columns=DATA_COLUMNS)
                skipped += len(chunk) - len(rows)
                if rows.empty:
                    continue
                count += len(rows)
                blueshifted += int(rows["redshift"].lt(0).sum())
                rows["name"] = names.loc[valid]
                rows["catalog_id"] = catalog.id
                rows["created_at"] = now
                rows["modified"] = now
                rows["healpix"] = HPX.lonlat_to_healpix(
                    rows["ra"].to_numpy() * u.deg, rows["dec"].to_numpy() * u.deg
                )
                copy.write(
                    rows.to_csv(
                        columns=COPY_COLUMNS, index=False, header=False, na_rep=""
                    )
                )
    if not count:
        raise ValueError("No valid Galaxy rows to import")
    return count, blueshifted, skipped
