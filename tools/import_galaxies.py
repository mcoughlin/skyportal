"""Import a prepared Galaxy catalog CSV into SkyPortal."""

from pathlib import Path

from baselayer.app.env import load_env, parser


def main():
    parser.description = __doc__
    parser.add_argument("--catalog-name", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--group-id", type=int, action="append", dest="group_ids")
    args, cfg = load_env()

    from skyportal.models import DBSession, init_db
    from skyportal.utils.galaxy_catalog_import import import_galaxies

    init_db(**cfg["database"])
    with DBSession() as session, session.begin():
        count, blueshifted, skipped = import_galaxies(
            session, args.input, args.catalog_name, group_ids=args.group_ids
        )
    print(
        f"Imported {count:,} Galaxy rows into {args.catalog_name} "
        f"({blueshifted:,} with negative redshifts, {skipped:,} skipped)"
    )


if __name__ == "__main__":
    main()
