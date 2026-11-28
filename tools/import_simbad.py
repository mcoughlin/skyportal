"""Import a matched pair of SIMBAD TAP CSV exports into SkyPortal."""

from pathlib import Path

from baselayer.app.env import load_env, parser


def main():
    parser.description = __doc__
    parser.add_argument("--basic", required=True, type=Path)
    parser.add_argument("--ident", required=True, type=Path)
    parser.add_argument("--release", required=True)
    parser.add_argument("--group-id", type=int, action="append", dest="group_ids")
    args, cfg = load_env()

    from skyportal.models import DBSession, init_db
    from skyportal.utils.catalog_import import import_simbad

    init_db(**cfg["database"])
    with DBSession() as session, session.begin():
        release = import_simbad(
            session, args.basic, args.ident, args.release, group_ids=args.group_ids
        )
        count = release.entries_count
    print(f"Activated SIMBAD {args.release} with {count:,} objects")


if __name__ == "__main__":
    main()
