"""
Prepare ABS geographies for the map view (SA2 or SA3) — v3.

STEP 1 — download the boundary shapefile (once) from the ABS:
  https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files
  -> "Statistical Area Level 3 (SA3) ASGS Ed 3 2021 ... Shapefile" (or SA2)

STEP 2 — run (from this data/ folder):
  pip install geopandas
  python prepare_geodata.py --shp /path/to/SA3_2021_AUST_GDA2020.shp --level sa3

Outputs:
  sa_<level>_boundaries.geojson  SA-only simplified boundaries (WGS84)
  sa_<level>_areas.csv           area reference: code, name, synthetic
                                 population, SEIFA quintile, remoteness

STEP 3 — re-run the pipeline so episodes pick up real area codes:
  python generate_episodes.py && python aggregate.py

The area reference is generated FROM the shapefile's own codes, so joins in
the apps can never mismatch. Replace population/SEIFA/remoteness with real
ABS ERP, IRSD quintile and ASGS remoteness lookups for production.
"""

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd

FIELDS = {"sa3": ("SA3_CODE21", "SA3_NAME21", "STE_NAME21"),
          "sa2": ("SA2_CODE21", "SA2_NAME21", "STE_NAME21")}
SEIFA = ["Q1 - most disadvantaged", "Q2", "Q3", "Q4", "Q5 - least disadvantaged"]
REMOTE = ["Major Cities of Australia", "Inner Regional Australia",
          "Outer Regional Australia", "Remote Australia",
          "Very Remote Australia"]

parser = argparse.ArgumentParser()
parser.add_argument("--shp", required=True)
parser.add_argument("--level", choices=["sa2", "sa3"], default="sa3")
args = parser.parse_args()
code_f, name_f, state_f = FIELDS[args.level]

gdf = gpd.read_file(args.shp)
gdf = gdf[(gdf[state_f] == "South Australia") & gdf.geometry.notna()].copy()
print(f"{len(gdf)} {args.level.upper()} areas in South Australia")

gdf = gdf.to_crs(epsg=4326)
gdf["geometry"] = gdf.geometry.simplify(0.005, preserve_topology=True)
gdf = gdf.rename(columns={code_f: "area_code", name_f: "area_name"})
gdf[["area_code", "area_name", "geometry"]].to_file(
    f"sa_{args.level}_boundaries.geojson", driver="GeoJSON")

# Synthetic area attributes, seeded from the code (reproducible)
rng = np.random.default_rng(2026)
recs = []
for _, r in gdf.iterrows():
    h = int(str(r["area_code"])[-3:])
    pop = int(rng.uniform(8_000, 45_000) if args.level == "sa3"
              else rng.uniform(2_000, 14_000))
    recs.append(dict(area_code=r["area_code"], area_name=r["area_name"],
                     population=pop, seifa_quintile=SEIFA[h % 5],
                     remoteness=REMOTE[min(h % 7, 4)]))
pd.DataFrame(recs).to_csv(f"sa_{args.level}_areas.csv", index=False)
print(f"Wrote sa_{args.level}_boundaries.geojson and sa_{args.level}_areas.csv")
print("Now re-run: python generate_episodes.py && python aggregate.py")
