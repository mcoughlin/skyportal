import { useState, type FormEvent } from "react";
import { skipToken } from "@reduxjs/toolkit/query";
import Button from "@mui/material/Button";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

import {
  useCrossmatchLocalCatalogsQuery,
  useLazyCrossmatchLocalCatalogsQuery,
  useLazyResolveLocalCatalogQuery,
  useListLocalCatalogsQuery,
  type Matches,
} from "../../ducks/localCatalogs";

const CatalogMatches = ({ data }: { data: Matches }) => (
  <>
    {data.matches.length ? (
      <ul>
        {data.matches.map((match) => (
          <li key={`${match.catalog}:${match.external_id}`}>
            {match.url ? (
              <Link href={match.url} target="_blank" rel="noopener noreferrer">
                {match.name}
              </Link>
            ) : (
              match.name
            )}{" "}
            ({match.catalog_name}
            {match.object_type ? `, ${match.object_type}` : ""})
            {match.match_type === "footprint"
              ? " · inside catalog footprint"
              : match.separation_arcsec != null
                ? ` · ${match.separation_arcsec.toFixed(2)}″ away`
                : match.ra != null && match.dec != null
                  ? ` · ${match.ra.toFixed(6)}°, ${match.dec.toFixed(6)}°`
                  : " · position unavailable"}
          </li>
        ))}
      </ul>
    ) : (
      <Typography>No catalog matches.</Typography>
    )}
    {data.truncated && <Typography>More matches are available.</Typography>}
  </>
);

export const SourceCatalogMatches = ({
  ra,
  dec,
  enabled,
}: {
  ra: number | null;
  dec: number | null;
  enabled: boolean;
}) => {
  const { data } = useCrossmatchLocalCatalogsQuery(
    enabled && ra != null && dec != null ? { ra, dec } : skipToken,
  );
  if (!data?.matches.length) {
    return null;
  }
  return (
    <Stack>
      <Typography variant="subtitle2">Local catalog matches</Typography>
      <CatalogMatches data={data} />
    </Stack>
  );
};

const CatalogSearch = () => {
  const { data: catalogs = [] } = useListLocalCatalogsQuery();
  const [catalog, setCatalog] = useState("");
  const [mode, setMode] = useState("name");
  const [resolve, named] = useLazyResolveLocalCatalogQuery();
  const [crossmatch, positional] = useLazyCrossmatchLocalCatalogsQuery();
  const result = mode === "name" ? named : positional;
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const scope = catalog ? { catalog } : {};
    if (mode === "name") {
      void resolve({ ...scope, name: String(values.get("name")) });
    } else {
      void crossmatch({
        ...scope,
        ra: Number(values.get("ra")),
        dec: Number(values.get("dec")),
        radius_arcsec: Number(values.get("radius")),
      });
    }
  };

  return (
    <Paper sx={{ m: 2, p: 2 }}>
      <Stack spacing={2}>
        <Typography variant="h6">Search catalogs</Typography>
        <Stack
          component="form"
          direction={{ xs: "column", md: "row" }}
          spacing={1}
          onSubmit={submit}
        >
          <TextField
            select
            size="small"
            label="Catalog"
            value={catalog}
            onChange={(event) => setCatalog(event.target.value)}
            sx={{ minWidth: "12rem" }}
          >
            <MenuItem value="">All catalogs</MenuItem>
            {catalogs.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                {item.name}
                {item.release ? ` (${item.release})` : ""}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Search by"
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            sx={{ minWidth: "8rem" }}
          >
            <MenuItem value="name">Name</MenuItem>
            <MenuItem value="position">Position</MenuItem>
          </TextField>
          {mode === "name" ? (
            <TextField name="name" size="small" label="Object name" required />
          ) : (
            <>
              <TextField
                name="ra"
                size="small"
                label="RA (°)"
                type="number"
                slotProps={{ htmlInput: { min: 0, max: 360, step: "any" } }}
                required
              />
              <TextField
                name="dec"
                size="small"
                label="Dec (°)"
                type="number"
                slotProps={{ htmlInput: { min: -90, max: 90, step: "any" } }}
                required
              />
              <TextField
                name="radius"
                size="small"
                label="Radius (″)"
                type="number"
                defaultValue={30}
                slotProps={{ htmlInput: { min: 0, max: 3600, step: "any" } }}
                required
              />
            </>
          )}
          <Button
            type="submit"
            variant="contained"
            disabled={result.isFetching}
          >
            Search
          </Button>
        </Stack>
        {result.isFetching && <Typography>Searching…</Typography>}
        {result.isError && (
          <Typography color="error">Catalog search failed.</Typography>
        )}
        {!result.isFetching && !result.isError && result.data && (
          <CatalogMatches data={result.data} />
        )}
      </Stack>
    </Paper>
  );
};

export default CatalogSearch;
