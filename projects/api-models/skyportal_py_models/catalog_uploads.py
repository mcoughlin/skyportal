"""Contracts for the resumable catalog upload API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_UPLOAD_BYTES = 128 * 1024**3


class CatalogUploadFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size: int = Field(gt=0, le=MAX_UPLOAD_BYTES)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    encoding: Literal["identity", "gzip"] = "identity"


class CatalogUploadManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["galaxy", "simbad"]
    catalog_name: str | None = Field(default=None, min_length=1, max_length=128)
    release: str | None = Field(default=None, min_length=1, max_length=128)
    group_ids: list[int] | None = Field(default=None, max_length=100)
    files: dict[str, CatalogUploadFile]

    @model_validator(mode="after")
    def check_files(self):
        if self.kind == "galaxy":
            if (
                not self.catalog_name
                or self.release is not None
                or set(self.files) != {"galaxies"}
            ):
                raise ValueError(
                    "Galaxy uploads require catalog_name and a galaxies file"
                )
        elif (
            not self.release
            or self.catalog_name is not None
            or set(self.files) != {"basic", "ident"}
        ):
            raise ValueError(
                "SIMBAD uploads require release and both basic and ident files"
            )
        if sum(file.size for file in self.files.values()) > MAX_UPLOAD_BYTES:
            raise ValueError("Upload exceeds the total size limit")
        return self


class CatalogUploadResult(BaseModel):
    rows_imported: int
    rows_skipped: int | None = None
    negative_redshifts: int | None = None


class CatalogUploadStatus(BaseModel):
    id: str
    status: Literal["uploading", "loading", "complete", "failed"]
    chunk_size: int
    received: dict[str, list[int]]
    result: CatalogUploadResult | None
    error: str | None
