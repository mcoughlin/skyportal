"""Import verified upload streams without copying them to local cloud storage."""

import gzip
import hashlib
import io
import logging
import zlib
from contextlib import ExitStack

import sqlalchemy as sa

from ..models import new_session
from ..models.catalog_upload import catalog_upload_chunks as chunks
from ..models.catalog_upload import catalog_uploads as uploads
from .catalog_import import import_simbad
from .galaxy_catalog_import import import_galaxies

log = logging.getLogger(__name__)
CHUNK_SIZE = 4 * 1024**2


class UploadedBytes(io.RawIOBase):
    """Read one staged chunk at a time and verify the complete byte stream."""

    def __init__(self, session, upload_id, name, file):
        super().__init__()
        self.session = session
        self.upload_id = upload_id
        self.name = name
        self.file = file
        self.digest = hashlib.sha256()
        self.count = 0
        self.pending = memoryview(b"")
        self.rows = None

    def readable(self):
        return True

    def readinto(self, target):
        if not self.pending:
            if self.rows is None:
                statement = (
                    sa.select(chunks.c.data)
                    .where(
                        chunks.c.upload_id == self.upload_id,
                        chunks.c.file_name == self.name,
                    )
                    .order_by(chunks.c.chunk_index)
                    .execution_options(yield_per=1)
                )
                self.rows = self.session.scalars(statement)
            data = next(self.rows, None)
            if data is None:
                return 0
            self.digest.update(data)
            self.count += len(data)
            self.pending = memoryview(data)
        size = min(len(target), len(self.pending))
        target[:size] = self.pending[:size]
        self.pending = self.pending[size:]
        return size

    def verify(self):
        scratch = bytearray(io.DEFAULT_BUFFER_SIZE)
        while self.readinto(scratch):
            pass
        if (
            self.count != self.file["size"]
            or self.digest.hexdigest() != self.file["sha256"]
        ):
            raise ValueError(f"Uploaded {self.name} file does not match its manifest")

    def close(self):
        if self.rows is not None:
            self.rows.close()
        super().close()


def load_upload(session, upload_id, manifest):
    """Load in the caller's transaction using a separate streaming connection for input."""
    with new_session() as reader, ExitStack() as stack:
        sources = {}
        raw_files = []
        for name, file in manifest["files"].items():
            raw = UploadedBytes(reader, upload_id, name, file)
            raw_files.append(raw)
            stream = stack.enter_context(io.BufferedReader(raw))
            if file["encoding"] == "gzip":
                stream = stack.enter_context(gzip.GzipFile(fileobj=stream))
            sources[name] = stack.enter_context(
                io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
            )

        groups = manifest.get("group_ids")
        if manifest["kind"] == "galaxy":
            count, blueshifted, skipped = import_galaxies(
                session, sources["galaxies"], manifest["catalog_name"], group_ids=groups
            )
            result = {
                "rows_imported": count,
                "rows_skipped": skipped,
                "negative_redshifts": blueshifted,
            }
        else:
            release = import_simbad(
                session,
                sources["basic"],
                sources["ident"],
                manifest["release"],
                group_ids=groups,
                allow_existing=False,
            )
            result = {"rows_imported": release.entries_count}
        for raw in raw_files:
            raw.verify()
        return result


def process_upload(upload_id):
    """Publish staged data once, including after an interrupted worker is retried."""
    with new_session() as session, session.begin():
        locked = session.scalar(
            sa.select(
                sa.func.pg_try_advisory_xact_lock(
                    sa.func.hashtextextended(upload_id, 0)
                )
            )
        )
        if not locked:
            return
        record = session.execute(
            sa.select(uploads.c.manifest).where(
                uploads.c.id == upload_id, uploads.c.status == "loading"
            )
        ).scalar_one_or_none()
        if record is None:
            return
        try:
            # Keep the worker lock while rolling back only the publication on failure.
            with session.begin_nested():
                result = load_upload(session, upload_id, record)
                published = session.execute(
                    uploads.update()
                    .where(uploads.c.id == upload_id, uploads.c.status == "loading")
                    .values(status="complete", result=result)
                )
                if published.rowcount != 1:
                    raise ValueError("Upload was removed during publication")
                session.execute(chunks.delete().where(chunks.c.upload_id == upload_id))
        except Exception as exc:
            log.exception("Catalog upload %s failed", upload_id)
            error = (
                str(exc)[:400]
                if isinstance(exc, (ValueError, OSError, EOFError, zlib.error))
                else "Catalog publication failed. Check the SkyPortal server logs."
            )
            session.execute(
                uploads.update()
                .where(uploads.c.id == upload_id)
                .values(status="failed", error=error)
            )
