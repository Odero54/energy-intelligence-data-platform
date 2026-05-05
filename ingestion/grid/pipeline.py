"""Download power transmission lines from OpenStreetMap (Overpass API) → RAW.GRID_INFRASTRUCTURE.

Uses the Overpass API to query ways tagged power=line|cable|minor_line within
each country's bounding box. Large countries are split into sub-quadrants to
avoid timeouts.

Re-runs are safe: already-cached countries are skipped and only newly fetched
countries are appended to Snowflake (no full truncate on re-run).
"""

import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from dotenv import load_dotenv
from shapely.geometry import LineString

load_dotenv()

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 180  # seconds per query
INTER_QUERY_SLEEP = 15  # seconds between sub-bbox queries
RETRY_WAIT = 90  # seconds to wait after a 429 before retrying
MAX_RETRIES = 3

# (lat_min, lon_min, lat_max, lon_max) — south, west, north, east
COUNTRY_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "KEN": (-4.7, 33.9, 5.0, 41.9),
    "NGA": (4.3, 2.7, 13.9, 14.7),
    "IND": (8.0, 68.1, 37.1, 97.4),
    "TZA": (-11.7, 29.3, -0.9, 40.4),
    "RWA": (-2.9, 28.9, -1.1, 30.9),
    "CIV": (4.3, -8.6, 10.7, -2.5),
    "PAK": (23.6, 60.9, 37.1, 77.8),
}

# Split into 2×2 sub-queries to avoid Overpass timeouts on large countries
LARGE_COUNTRIES = {"IND", "NGA"}

RAW_DIR = Path(__file__).parents[2] / "data" / "raw" / "grid"

OUTPUT_COLS = [
    "feature_id",
    "country_code",
    "feature_type",
    "voltage_kv",
    "status",
    "source_dataset",
    "geometry_wkt",
    "_source_file",
]

_HEADERS = {
    "User-Agent": "energy-intelligence-data-platform/1.0 (portfolio project)",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _overpass_query(bbox: tuple[float, float, float, float]) -> list[dict]:
    """Run a single Overpass bbox query with retry on 429."""
    lat_min, lon_min, lat_max, lon_max = bbox
    query = (
        f"[out:json][timeout:{OVERPASS_TIMEOUT}];"
        f'(way["power"~"^(line|cable|minor_line)$"]'
        f"({lat_min},{lon_min},{lat_max},{lon_max}););"
        f"out geom;"
    )
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers=_HEADERS,
            timeout=OVERPASS_TIMEOUT + 30,
        )
        if resp.status_code == 429:
            if attempt < MAX_RETRIES:
                print(
                    f"    Rate limited (429) — waiting {RETRY_WAIT}s before retry {attempt}/{MAX_RETRIES - 1}..."
                )
                time.sleep(RETRY_WAIT)
                continue
        resp.raise_for_status()
        return resp.json().get("elements", [])
    return []  # unreachable but satisfies type checker


def _bbox_quadrants(
    bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    lat_min, lon_min, lat_max, lon_max = bbox
    lat_mid = (lat_min + lat_max) / 2
    lon_mid = (lon_min + lon_max) / 2
    return [
        (lat_min, lon_min, lat_mid, lon_mid),
        (lat_min, lon_mid, lat_mid, lon_max),
        (lat_mid, lon_min, lat_max, lon_mid),
        (lat_mid, lon_mid, lat_max, lon_max),
    ]


def _elements_to_gdf(elements: list[dict], iso3: str) -> gpd.GeoDataFrame:
    rows = []
    seen_ids: set[int] = set()
    for el in elements:
        if el.get("type") != "way" or "geometry" not in el:
            continue
        eid = el["id"]
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        coords = [(n["lon"], n["lat"]) for n in el["geometry"]]
        if len(coords) < 2:
            continue
        tags = el.get("tags", {})
        rows.append(
            {
                "feature_id": str(eid),
                "country_code": iso3,
                "feature_type": tags.get("power", "line"),
                "voltage_kv": tags.get("voltage", ""),
                "status": tags.get("construction", "operational"),
                "source_dataset": "OpenStreetMap",
                "geometry": LineString(coords),
                "_source_file": f"osm_{iso3.lower()}_power_lines",
            }
        )
    if not rows:
        return gpd.GeoDataFrame(columns=["feature_id", "geometry"], crs="EPSG:4326")
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def extract_country(iso3: str) -> tuple[gpd.GeoDataFrame, bool]:
    """Return (GeoDataFrame, is_new). is_new=False when loaded from cache."""
    cache = RAW_DIR / f"grid_{iso3.lower()}.parquet"
    if cache.exists():
        print(f"    Using cached grid data for {iso3}")
        return gpd.read_parquet(cache), False

    bbox = COUNTRY_BOUNDS[iso3]
    bboxes = _bbox_quadrants(bbox) if iso3 in LARGE_COUNTRIES else [bbox]

    all_elements: list[dict] = []
    for i, sub_bbox in enumerate(bboxes):
        if len(bboxes) > 1:
            print(f"    Querying quadrant {i + 1}/{len(bboxes)}...")
        elements = _overpass_query(sub_bbox)
        all_elements.extend(elements)
        if i < len(bboxes) - 1:
            time.sleep(INTER_QUERY_SLEEP)

    gdf = _elements_to_gdf(all_elements, iso3)
    gdf.to_parquet(cache)
    return gdf, True


def transform(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    df = gdf.copy()
    df["geometry_wkt"] = df["geometry"].apply(lambda g: g.wkt if g is not None else "")
    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = ""
    return df[OUTPUT_COLS]


def run(dry_run: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_dfs: list[pd.DataFrame] = []

    for iso3 in COUNTRY_BOUNDS:
        print(f"  Fetching grid lines for {iso3}...")
        try:
            gdf, is_new = extract_country(iso3)
            df = transform(gdf)
            all_dfs.append(df)
            print(f"    {len(df)} features{'  (new)' if is_new else '  (cached)'}")
        except Exception as e:
            print(f"    ERROR for {iso3}: {e}")

    if not all_dfs:
        raise RuntimeError("No grid data retrieved for any country.")

    combined = pd.concat(all_dfs, ignore_index=True)
    (RAW_DIR / "grid_all.parquet").write_bytes(combined.to_parquet())
    print(f"  Total: {len(combined)} features across {len(all_dfs)} countries")

    if not dry_run:
        from ingestion._snowflake import upsert_dataframe

        # Upsert all fetched features — idempotent across re-runs.
        # Deduplication on (country_code, feature_id) handles OSM ways that
        # appear in multiple bbox quadrants for the same country.
        n_ins, n_upd = upsert_dataframe(
            combined,
            "GRID_INFRASTRUCTURE",
            merge_keys=["country_code", "feature_id"],
        )
        print(f"  Upserted → RAW.GRID_INFRASTRUCTURE: {n_ins} inserted, {n_upd} updated")
    else:
        print("  Dry run — skipping Snowflake load")


if __name__ == "__main__":
    run()
