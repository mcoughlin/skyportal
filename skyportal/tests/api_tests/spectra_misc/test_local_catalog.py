from pathlib import Path

import pytest
import sqlalchemy as sa
from psycopg.errors import ForeignKeyViolation

from skyportal.models import DBSession, Galaxy, GalaxyCatalog, SpatialCatalog
from skyportal.tests import api, assert_api, retry_until
from skyportal.tests.api_tests.test_mcp import call_tool
from skyportal.utils.catalog_import import import_simbad
from skyportal.utils.galaxy_catalog_import import import_galaxies

SIMBAD = Path(__file__).resolve().parents[2] / "data" / "simbad"


def get(endpoint, token, **params):
    status, response = api("GET", endpoint, token=token, params=params)
    assert_api(status, response)
    return response["data"]


@pytest.fixture
def simbad(public_group):
    with DBSession.session_factory.begin() as session:
        release = import_simbad(
            session,
            SIMBAD / "basic.csv",
            SIMBAD / "ident.csv",
            "fixture-v1",
            group_ids=[public_group.id],
        )
        catalog_id = release.catalog_id
    yield f"spatial:{catalog_id}"
    with DBSession.session_factory.begin() as session:
        session.execute(
            sa.delete(SpatialCatalog).where(SpatialCatalog.id == catalog_id)
        )


def test_simbad_import_and_search(
    simbad, view_only_token, view_only_token_no_groups, tmp_path
):
    visible = get("catalogs", view_only_token)
    simbad_catalog = next(row for row in visible if row["id"] == simbad)
    assert simbad_catalog["entries_count"] == 3
    assert simbad_catalog["release"] == "fixture-v1"
    assert simbad_catalog["geometry"] == "point"

    for name in ("M31", "ngc 224"):
        data = get("catalogs/resolve", view_only_token, catalog=simbad, name=name)
        assert [row["external_id"] for row in data["matches"]] == ["101"]
        assert data["matches"][0]["name"] == "M  31"
        assert data["matches"][0]["ra"] == pytest.approx(10.6847083333)

    unlocated = get(
        "catalogs/resolve", view_only_token, catalog=simbad, name="Fixture unlocated"
    )
    assert unlocated["matches"][0]["ra"] is None

    params = {
        "catalog": simbad,
        "ra": 10.6847083333,
        "dec": 41.26875,
        "radius_arcsec": 5,
    }
    nearby = get("catalogs/crossmatch", view_only_token, **params)["matches"]
    assert [row["external_id"] for row in nearby] == ["101", "102"]
    assert all(row["match_type"] == "point" for row in nearby)
    assert nearby[0]["separation_arcsec"] == pytest.approx(0)
    assert 3 < nearby[1]["separation_arcsec"] < 4
    assert get("catalogs/crossmatch", view_only_token, **params, limit=1)["truncated"]

    hidden = get("catalogs", view_only_token_no_groups)
    assert not any(row["id"] == simbad for row in hidden)
    hidden_search = get("catalogs/resolve", view_only_token_no_groups, name="NGC 224")
    assert not any(row["catalog"] == simbad for row in hidden_search["matches"])
    status, _ = api(
        "GET", "catalogs/crossmatch", token=view_only_token_no_groups, params=params
    )
    assert status == 400

    is_error, tool_result, _ = call_tool(
        "resolve_catalog_object", {"name": "NGC 224"}, view_only_token
    )
    assert not is_error
    assert "M  31" in tool_result

    is_error, tool_result, _ = call_tool(
        "crossmatch_catalogs",
        {"ra": params["ra"], "dec": params["dec"]},
        view_only_token,
    )
    assert not is_error
    assert "separation_arcsec" in tool_result
    is_error, tool_result, _ = call_tool(
        "resolve_catalog_object", {"name": "NGC 224"}, view_only_token_no_groups
    )
    assert not is_error
    assert "M  31" not in tool_result

    broken = tmp_path / "ident.csv"
    broken.write_text("oidref,id\n9999,Dangling alias\n")
    with (
        pytest.raises(ForeignKeyViolation),
        DBSession.session_factory.begin() as session,
    ):
        import_simbad(session, SIMBAD / "basic.csv", broken, "fixture-v2")
    assert get("catalogs/crossmatch", view_only_token, **params)["matches"] == nearby

    with DBSession.session_factory.begin() as session:
        import_simbad(session, SIMBAD / "basic.csv", SIMBAD / "ident.csv", "fixture-v2")
    assert {
        row["release"]
        for row in get("catalogs/crossmatch", view_only_token, **params)["matches"]
    } == {"fixture-v2"}


def test_shared_catalogs_include_galaxies_and_legacy_footprints(
    public_group, super_admin_token, view_only_token, tmp_path
):
    for old_import in ("regalade", "ned"):
        status, _ = api(
            "POST", f"galaxy_catalog/{old_import}", token=super_admin_token, data={}
        )
        assert status == 405

    prepared = tmp_path / "galaxies.csv"
    prepared.write_text(
        'name,ra,dec,redshift\n"Fixture, galaxy",35,50,-0.001\nInvalid,35,91,\n'
    )
    catalog_name = "Shared API galaxy fixture"
    with DBSession.session_factory.begin() as session:
        assert import_galaxies(
            session, prepared, catalog_name, group_ids=[public_group.id]
        ) == (1, 1, 1)
        galaxy = session.scalar(
            sa.select(Galaxy).where(Galaxy.name == "Fixture, galaxy")
        )
        galaxy_id = galaxy.id
        galaxy_catalog_id = galaxy.catalog_id

    footprint_ids = []
    try:
        for suffix in ("a", "b"):
            status, data = api(
                "POST",
                "spatial_catalog",
                token=super_admin_token,
                data={
                    "catalog_name": f"Shared API footprint fixture {suffix}",
                    "group_ids": [public_group.id],
                    "catalog_data": {
                        "name": ["Same footprint name"],
                        "ra": [35],
                        "dec": [50],
                        "radius": [0.1],
                    },
                },
            )
            assert_api(status, data)
            footprint_ids.append(data["data"]["id"])

        def check():
            matches = get("catalogs/crossmatch", view_only_token, ra=35, dec=50)[
                "matches"
            ]
            assert any(
                match["catalog"] == f"galaxy:{galaxy_catalog_id}"
                and match["external_id"] == str(galaxy_id)
                and match["match_type"] == "point"
                and match["redshift"] == pytest.approx(-0.001)
                for match in matches
            )
            footprints = {
                match["catalog"]
                for match in matches
                if match["match_type"] == "footprint"
                and match["name"] == "Same-footprint-name"
            }
            assert footprints == {
                f"spatial:{catalog_id}" for catalog_id in footprint_ids
            }

        retry_until(check, timeout=30)
    finally:
        with DBSession.session_factory.begin() as session:
            session.execute(
                sa.delete(SpatialCatalog).where(SpatialCatalog.id.in_(footprint_ids))
            )
            session.execute(
                sa.delete(GalaxyCatalog).where(GalaxyCatalog.id == galaxy_catalog_id)
            )
