import gzip
import hashlib
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa

from skyportal.models import DBSession, GalaxyCatalog, SpatialCatalog
from skyportal.tests import api, assert_api, cfg, retry_until, session
from skyportal.utils.catalog_upload import CHUNK_SIZE

UPLOADS = "catalogs/uploads"
SIMBAD = Path(__file__).resolve().parents[2] / "data" / "simbad"


def manifest_file(data, encoding="identity"):
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "encoding": encoding,
    }


def call(method, endpoint, token, **kwargs):
    status, payload = api(method, endpoint, token=token, **kwargs)
    assert_api(status, payload)
    return payload["data"]


def put(upload_id, filename, index, data, token):
    return session.put(
        f"http://localhost:{cfg['ports.app']}/api/{UPLOADS}/{upload_id}/{filename}/{index}",
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Content-Type": "application/octet-stream",
        },
        timeout=30,
    )


def wait_for(upload_id, token, state):
    final = None

    def check():
        nonlocal final
        final = call("GET", f"{UPLOADS}/{upload_id}", token)
        assert final["status"] == state, final

    retry_until(check, timeout=30)
    return final


def test_resumable_galaxy_catalog_upload(
    super_admin_token, view_only_token, public_group
):
    token = super_admin_token
    name = f"Bulk Galaxy {uuid4()}"
    # Blank lines keep the fixture tiny in rows while exercising multiple HTTP chunks.
    data = b"name,ra,dec,redshift\nExample Galaxy,89,36,-0.003\n" + b"\n" * CHUNK_SIZE
    manifest = {
        "kind": "galaxy",
        "catalog_name": name,
        "group_ids": [public_group.id],
        "files": {"galaxies": manifest_file(data)},
    }
    try:
        status, _ = api("POST", UPLOADS, token=view_only_token, data=manifest)
        assert status == 403
        created = call("POST", UPLOADS, token, data=manifest)
        upload_id = created["id"]
        assert created["chunk_size"] == CHUNK_SIZE
        assert created["status"] == "uploading"
        assert created["received"] == {"galaxies": []}

        # Stage the last chunk first, then recover the upload from its manifest.
        tail = data[CHUNK_SIZE:]
        assert put(upload_id, "galaxies", 1, tail, token).status_code == 200
        assert put(upload_id, "galaxies", 1, tail, token).status_code == 200
        assert put(upload_id, "galaxies", 1, b"x" + tail[1:], token).status_code == 409
        resumed = call("POST", UPLOADS, token, data=manifest)
        assert resumed["id"] == upload_id
        assert resumed["received"] == {"galaxies": [1]}
        status, _ = api("POST", f"{UPLOADS}/{upload_id}/finalize", token=token)
        assert status == 409

        assert (
            put(upload_id, "galaxies", 0, data[:CHUNK_SIZE], token).status_code == 200
        )
        call("POST", f"{UPLOADS}/{upload_id}/finalize", token)
        completed = wait_for(upload_id, token, "complete")
        assert completed["result"] == {
            "rows_imported": 1,
            "negative_redshifts": 1,
            "rows_skipped": 0,
        }
        assert call("POST", f"{UPLOADS}/{upload_id}/finalize", token) == completed
        matches = call(
            "GET",
            "catalogs/resolve",
            view_only_token,
            params={"name": "Example Galaxy"},
        )["matches"]
        assert any(
            match["catalog_name"] == name and match["redshift"] == -0.003
            for match in matches
        )
    finally:
        with DBSession.session_factory.begin() as db:
            db.execute(sa.delete(GalaxyCatalog).where(GalaxyCatalog.name == name))


def test_publish_simbad_only_after_both_files_validate(
    super_admin_token, view_only_token, public_group
):
    token = super_admin_token
    sources = {
        name: gzip.compress((SIMBAD / f"{name}.csv").read_bytes())
        for name in ("basic", "ident")
    }
    manifest = {
        "kind": "simbad",
        "release": f"upload-fixture-{uuid4()}",
        "group_ids": [public_group.id],
        "files": {name: manifest_file(data, "gzip") for name, data in sources.items()},
    }
    try:
        broken = {
            **manifest,
            "files": {
                **manifest["files"],
                "ident": {**manifest["files"]["ident"], "sha256": "0" * 64},
            },
        }
        for body, state in ((broken, "failed"), (manifest, "complete")):
            upload_id = call("POST", UPLOADS, token, data=body)["id"]
            for name, data in sources.items():
                assert put(upload_id, name, 0, data, token).status_code == 200
            call("POST", f"{UPLOADS}/{upload_id}/finalize", token)
            result = wait_for(upload_id, token, state)
            matches = call(
                "GET", "catalogs/resolve", view_only_token, params={"name": "M31"}
            )["matches"]
            releases = {row["release"] for row in matches}
            if state == "failed":
                assert "does not match its manifest" in result["error"]
                assert manifest["release"] not in releases
                status, _ = api("DELETE", f"{UPLOADS}/{upload_id}", token=token)
                assert status == 200
            else:
                assert result["result"]["rows_imported"] == 3
                assert manifest["release"] in releases
    finally:
        with DBSession.session_factory.begin() as db:
            db.execute(
                sa.delete(SpatialCatalog).where(SpatialCatalog.catalog_name == "SIMBAD")
            )
