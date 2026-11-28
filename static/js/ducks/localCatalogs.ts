import { buildQueryString } from "../API";
import { skyportalApi } from "../api/skyportalApi";

interface Catalog {
  id: string;
  name: string;
  geometry: "point" | "footprint";
  release: string | null;
  entries_count: number | null;
}

interface Match {
  catalog: string;
  catalog_name: string;
  release: string | null;
  external_id: string;
  name: string;
  ra: number | null;
  dec: number | null;
  match_type?: "point" | "footprint";
  separation_arcsec?: number;
  object_type?: string | null;
  url?: string;
}

interface Matches {
  matches: Match[];
  truncated: boolean;
}

interface Cone {
  ra: number;
  dec: number;
  radius_arcsec?: number;
  catalog?: string;
}

const localCatalogsApi = skyportalApi.injectEndpoints({
  endpoints: (build) => ({
    listLocalCatalogs: build.query<Catalog[], void>({
      query: () => "api/catalogs",
      providesTags: ["SpatialCatalogs", "Galaxies"],
    }),
    resolveLocalCatalog: build.query<
      Matches,
      { name: string; catalog?: string }
    >({
      query: (params) =>
        `api/catalogs/resolve?${buildQueryString({ ...params })}`,
    }),
    crossmatchLocalCatalogs: build.query<Matches, Cone>({
      query: (params) =>
        `api/catalogs/crossmatch?${buildQueryString({ ...params })}`,
    }),
  }),
});

export const {
  useListLocalCatalogsQuery,
  useLazyResolveLocalCatalogQuery,
  useLazyCrossmatchLocalCatalogsQuery,
  useCrossmatchLocalCatalogsQuery,
} = localCatalogsApi;
export type { Matches };
