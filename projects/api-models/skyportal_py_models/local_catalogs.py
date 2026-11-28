"""Request and response schemas for SkyPortal's local catalog API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class LocalCatalogResponse(BaseModel):
    id: str
    legacy_id: int
    name: str
    geometry: Literal["point", "footprint"]
    url: str | None
    release: str | None
    entries_count: int | None


class LocalCatalogListResponse(RootModel[list[LocalCatalogResponse]]):
    pass


class CatalogSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    catalog: str | None = Field(
        default=None,
        pattern=r"^(spatial|galaxy):[0-9]{1,10}$",
        description="Optional catalog ID from GET /api/catalogs.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class CatalogResolveQuery(CatalogSearchQuery):
    name: str = Field(min_length=1, max_length=256, description="Name or alias.")


class CatalogCrossmatchQuery(CatalogSearchQuery):
    ra: float = Field(ge=0, lt=360, description="Right ascension in degrees.")
    dec: float = Field(ge=-90, le=90, description="Declination in degrees.")
    radius_arcsec: float = Field(
        default=30, gt=0, le=3600, description="Point search radius in arcseconds."
    )


class CatalogMatchResponse(BaseModel):
    catalog: str
    catalog_name: str
    release: str | None
    external_id: str
    name: str
    ra: float | None
    dec: float | None
    matched_alias: str | None = None
    match_type: Literal["point", "footprint"] | None = None
    separation_arcsec: float | None = None
    object_type: str | None = None
    redshift: float | None = None
    coordinate_bibcode: str | None = None
    url: str | None = None


class CatalogSearchResponse(BaseModel):
    matches: list[CatalogMatchResponse]
    truncated: bool
