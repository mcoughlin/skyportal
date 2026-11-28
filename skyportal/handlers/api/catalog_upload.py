"""Authenticated, resumable staging and publication for catalog imports."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import sqlalchemy as sa
from skyportal_py_models.catalog_uploads import (
    CatalogUploadManifest,
    CatalogUploadStatus,
)
from sqlalchemy.dialects.postgresql import insert
from tornado.ioloop import IOLoop

from baselayer.app.access import permissions
from baselayer.app.models import UserAccessControl

from ...models.catalog_upload import catalog_upload_chunks as chunks
from ...models.catalog_upload import catalog_uploads as uploads
from ...utils.catalog_groups import resolve_groups
from ...utils.catalog_upload import CHUNK_SIZE, process_upload
from ..base import BaseHandler

_workers = ThreadPoolExecutor(max_workers=1, thread_name_prefix="catalog-upload")
_scheduled = set()


def schedule_upload(upload_id):
    if upload_id in _scheduled:
        return
    _scheduled.add(upload_id)
    future = IOLoop.current().run_in_executor(_workers, process_upload, upload_id)
    future.add_done_callback(lambda _: _scheduled.discard(upload_id))


def upload_query(session, upload_id):
    owner_id = UserAccessControl.user_id_from_user_or_token(session.user_or_token)
    return sa.select(uploads).where(
        uploads.c.id == upload_id, uploads.c.owner_id == owner_id
    )


async def describe_upload(session, row):
    received = {name: [] for name in row.manifest["files"]}
    if row.status == "uploading":
        statement = (
            sa.select(chunks.c.file_name, chunks.c.chunk_index)
            .where(chunks.c.upload_id == row.id)
            .order_by(chunks.c.file_name, chunks.c.chunk_index)
        )
        for name, index in await session.execute(statement):
            received[name].append(index)
    return {
        "id": row.id,
        "status": row.status,
        "chunk_size": CHUNK_SIZE,
        "received": received,
        "result": row.result,
        "error": row.error,
    }


class CatalogUploadHandler(BaseHandler):
    @permissions(["System admin"])
    async def post(self, *, body: CatalogUploadManifest = None) -> CatalogUploadStatus:
        """
        ---
        summary: Create or resume a catalog upload
        description: An identical manifest from the same owner resumes the upload.
        tags:
          - catalogs
        """
        body = self.parse_body(CatalogUploadManifest)
        manifest = body.model_dump(mode="json", exclude_none=True)
        if body.group_ids:
            manifest["group_ids"] = sorted(set(body.group_ids))
        else:
            manifest.pop("group_ids", None)
        fingerprint = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()
        async with self.AsyncSession() as session:
            if body.group_ids:
                try:
                    await resolve_groups(session, session.user_or_token, body.group_ids)
                except ValueError as exc:
                    return self.error(str(exc))
            owner_id = UserAccessControl.user_id_from_user_or_token(
                session.user_or_token
            )
            await session.execute(
                insert(uploads)
                .values(
                    id=str(uuid4()),
                    owner_id=owner_id,
                    manifest=manifest,
                    fingerprint=fingerprint,
                )
                .on_conflict_do_nothing(
                    index_elements=[uploads.c.owner_id, uploads.c.fingerprint]
                )
            )
            statement = sa.select(uploads).where(
                uploads.c.owner_id == owner_id, uploads.c.fingerprint == fingerprint
            )
            row = (await session.execute(statement)).one()
            data = await describe_upload(session, row)
            await session.commit()
        if row.status == "loading":
            schedule_upload(row.id)
        return self.success(data=data)


class CatalogUploadStatusHandler(BaseHandler):
    @permissions(["System admin"])
    async def get(self, upload_id: str) -> CatalogUploadStatus:
        """
        ---
        summary: Get catalog upload progress and publication result
        tags:
          - catalogs
        """
        async with self.AsyncSession() as session:
            row = (
                await session.execute(upload_query(session, upload_id))
            ).one_or_none()
            if row is None:
                return self.error("Catalog upload not found", status=404)
            data = await describe_upload(session, row)
        if row.status == "loading":
            schedule_upload(row.id)
        return self.success(data=data)

    @permissions(["System admin"])
    async def delete(self, upload_id: str):
        """
        ---
        summary: Discard staged files for an uploading or failed catalog upload
        tags:
          - catalogs
        responses:
          200:
            description: The upload was discarded.
        """
        async with self.AsyncSession() as session:
            row = (
                await session.execute(
                    upload_query(session, upload_id).with_for_update()
                )
            ).one_or_none()
            if row is None:
                return self.error("Catalog upload not found", status=404)
            if row.status not in ("uploading", "failed"):
                return self.error(
                    "Only uploading or failed uploads can be discarded", status=409
                )
            await session.execute(uploads.delete().where(uploads.c.id == upload_id))
            await session.commit()
        return self.success()


class CatalogUploadChunkHandler(BaseHandler):
    @permissions(["System admin"])
    async def put(self, upload_id: str, file_name: str, chunk_index: int):
        """
        ---
        summary: Upload one catalog file chunk
        description: Send application/octet-stream. Repeating an identical chunk is safe.
        tags:
          - catalogs
        requestBody:
          required: true
          content:
            application/octet-stream:
              schema:
                type: string
                format: binary
        responses:
          200:
            description: The chunk has been stored.
        """
        if (
            self.request.headers.get("Content-Type", "")
            .split(";", 1)[0]
            .strip()
            .lower()
            != "application/octet-stream"
        ):
            return self.error("Use Content-Type application/octet-stream", status=415)
        body = self.request.body
        if not 0 < len(body) <= CHUNK_SIZE:
            return self.error("Invalid catalog upload chunk size", status=400)
        digest = hashlib.sha256(body).hexdigest()
        async with self.AsyncSession() as session:
            row = (
                await session.execute(
                    upload_query(session, upload_id).with_for_update()
                )
            ).one_or_none()
            if row is None:
                return self.error("Catalog upload not found", status=404)
            if row.status != "uploading":
                return self.error(
                    "Catalog upload is no longer accepting chunks", status=409
                )
            file = row.manifest["files"].get(file_name)
            remaining = file["size"] - chunk_index * CHUNK_SIZE if file else 0
            if (
                chunk_index < 0
                or remaining <= 0
                or len(body) != min(CHUNK_SIZE, remaining)
            ):
                return self.error("Invalid file, chunk index or chunk size")
            key = {
                "upload_id": upload_id,
                "file_name": file_name,
                "chunk_index": chunk_index,
            }
            existing = await session.scalar(sa.select(chunks.c.sha256).filter_by(**key))
            if existing is not None and existing != digest:
                return self.error(
                    "Chunk already exists with different bytes", status=409
                )
            if existing is None:
                await session.execute(
                    chunks.insert().values(**key, sha256=digest, data=body)
                )
                await session.commit()
        return self.success(data={"index": chunk_index})


class CatalogUploadFinalizeHandler(BaseHandler):
    @permissions(["System admin"])
    async def post(self, upload_id: str) -> CatalogUploadStatus:
        """
        ---
        summary: Start or resume publication of a complete catalog upload
        tags:
          - catalogs
        """
        async with self.AsyncSession() as session:
            statement = upload_query(session, upload_id)
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                return self.error("Catalog upload not found", status=404)
            if row.status in ("uploading", "failed"):
                row = (await session.execute(statement.with_for_update())).one_or_none()
                if row is None:
                    return self.error("Catalog upload not found", status=404)
                if row.status in ("uploading", "failed"):
                    counts = dict(
                        (
                            await session.execute(
                                sa.select(chunks.c.file_name, sa.func.count())
                                .where(chunks.c.upload_id == upload_id)
                                .group_by(chunks.c.file_name)
                            )
                        ).all()
                    )
                    for name, file in row.manifest["files"].items():
                        required = (file["size"] + CHUNK_SIZE - 1) // CHUNK_SIZE
                        if counts.get(name, 0) != required:
                            return self.error(
                                f"Upload is missing chunks for {name}", status=409
                            )
                    row = (
                        await session.execute(
                            uploads.update()
                            .where(uploads.c.id == upload_id)
                            .values(status="loading", error=None)
                            .returning(uploads)
                        )
                    ).one()
                    await session.commit()
            data = await describe_upload(session, row)
        if row.status == "loading":
            schedule_upload(row.id)
        return self.success(data=data)
