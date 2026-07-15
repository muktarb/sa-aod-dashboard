"""
Aggregate synthetic episodes into the published cube the apps read (v3).

  sa_aod_episodes.csv + diagnosis_ref.csv
      -> sa_aod_hospitalisations.csv   (cube: counts, rates, 95% CIs,
                                        mean bed days; NSW-style group_by)
      -> sa_<level>_map.csv            (per area x drug group: episodes,
                                        population, rate, SEIFA quintile
                                        for the map hover; needs geodata)

Bed days follow the AIHW convention: date of discharge minus date of
admission, with same-day episodes counted as 1 patient day.

Run:  python aggregate.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

LATEST = "2024-25"
STATE = "South Australia (All LHNs)"
ALLDRUG = "All drug-related"

LHN_POP = {"Central Adelaide LHN": 490_000, "Northern Adelaide LHN": 420_000,
           "Southern Adelaide LHN": 400_000,
           "Barossa Hills Fleurieu LHN": 165_000,
           "Eyre and Far North LHN": 55_000,
           "Flinders and Upper North LHN": 70_000,
           "Limestone Coast LHN": 65_000,
           "Riverland Mallee Coorong LHN": 70_000,
           "Yorke and Northern LHN": 75_000}
LHN_POP[STATE] = sum(LHN_POP.values())

DIM_SHARE = {   # population share of each breakdown level (within any LHN)
    "sex": {"Males": 0.50, "Females": 0.50},
    "age_group": {"0-14": 0.18, "15-24": 0.12, "25-34": 0.14, "35-44": 0.13,
                  "45-54": 0.13, "55-64": 0.12, "65+": 0.18},
    "indigenous_status": {"Non-Indigenous": 0.975, "First Nations": 0.025},
    "seifa_quintile": {"Q1 - most disadvantaged": 0.20, "Q2": 0.20, "Q3": 0.20,
                       "Q4": 0.20, "Q5 - least disadvantaged": 0.20},
    "remoteness": {"Major Cities of Australia": 0.74,
                   "Inner Regional Australia": 0.12,
                   "Outer Regional Australia": 0.10,
                   "Remote Australia": 0.03, "Very Remote Australia": 0.01},
}
DEFAULTS = dict(sex="Persons", age_group="All ages", indigenous_status="All",
                seifa_quintile="All", remoteness="All")
GROWTH = 1.012

# ---- Load and enrich episodes -------------------------------------------------
ep = pd.read_csv("sa_aod_episodes.csv")
ref = pd.read_csv("diagnosis_ref.csv")
ep = ep.merge(ref[["diagnosis_code", "diagnosis_group"]],
              on="diagnosis_code", how="left")
assert ep.diagnosis_group.notna().all(), "Unmapped diagnosis codes"

adm = pd.to_datetime(ep.AdmDateTime)
dis = pd.to_datetime(ep.DischSummaryDtm)
ep["bed_days"] = np.maximum(
    (dis.dt.normalize() - adm.dt.normalize()).dt.days, 1)   # AIHW convention

# Duplicate every episode under 'All drug-related' so totals fall out of groupby
ep_all = ep.copy()
ep_all["diagnosis_group"] = ALLDRUG
ep = pd.concat([ep, ep_all], ignore_index=True)

# Duplicate every episode under statewide so STATE totals fall out of groupby
ep_state = ep.copy()
ep_state["lhn"] = STATE
ep = pd.concat([ep, ep_state], ignore_index=True)


def pop_for(lhn, year_i, dim_col=None, level=None):
    p = LHN_POP[lhn] * GROWTH ** year_i
    if dim_col:
        p *= DIM_SHARE[dim_col][level]
    return p


def summarise(g, group_by, **dims):
    out = (g.groupby(["diagnosis_group", "lhn", "financial_year",
                      "year_start"] + list(dims.values()), observed=True)
             .agg(count=("episode_id", "size"),
                  mean_bed_days=("bed_days", "mean")).reset_index())
    out["group_by"] = group_by
    for k, v in dims.items():                       # rename dim col to schema
        out = out.rename(columns={v: k}) if k != v else out
    return out


frames = [summarise(ep, "Total")]
for label, col in [("Sex", "sex"), ("Age group", "age_group"),
                   ("Indigenous status", "indigenous_status"),
                   ("SEIFA quintile", "seifa_quintile"),
                   ("Remoteness", "remoteness")]:
    frames.append(summarise(ep, label, **{col: col}))
frames.append(summarise(ep, "Sex by age", sex="sex", age_group="age_group"))

cube = pd.concat(frames, ignore_index=True)
for k, v in DEFAULTS.items():
    if k not in cube:
        cube[k] = v
    cube[k] = cube[k].fillna(v)

# Population, rate, CI per row
def row_pop(r):
    p = LHN_POP[r.lhn] * GROWTH ** (r.year_start - 2020)
    for col in DIM_SHARE:
        if r[col] not in ("Persons", "All ages", "All"):
            p *= DIM_SHARE[col][r[col]]
    return p


cube["population"] = cube.apply(row_pop, axis=1).astype(int)
cube["rate_per_100k"] = (cube["count"] / cube.population * 1e5).round(1)
se = np.sqrt(cube["count"].clip(lower=1)) / cube.population * 1e5
cube["rate_lcl"] = (cube.rate_per_100k - 1.96 * se).clip(lower=0).round(1)
cube["rate_ucl"] = (cube.rate_per_100k + 1.96 * se).round(1)
cube["mean_bed_days"] = cube.mean_bed_days.round(2)
cube.insert(0, "indicator", "Alcohol and other drug-related hospitalisations")
cube = cube.rename(columns={"diagnosis_group": "drug_type"})
cube.to_csv("sa_aod_hospitalisations.csv", index=False)
print(f"Wrote sa_aod_hospitalisations.csv: {len(cube):,} rows, "
      f"{cube.drug_type.nunique()} drug groups")

# ---- Data currency metadata for the apps ---------------------------------------
import json
from datetime import datetime

meta = {
    "data_as_of": str(dis.max().date()),          # latest discharge in the data
    "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "reporting_period": f"{'2020-21'} to {LATEST}",
    "version": "v4",
}
with open("data_metadata.json", "w") as f:
    json.dump(meta, f, indent=2)
print(f"Wrote data_metadata.json: {meta}")

# ---- Area-level map file (only if geodata prepared) ----------------------------
for level in ("sa3", "sa2"):
    code_col, areas_f = f"{level}_code", Path(f"sa_{level}_areas.csv")
    if code_col in ep.columns and areas_f.exists():
        areas = pd.read_csv(areas_f, dtype={"area_code": str})
        e = ep[(ep.lhn != STATE) & (ep.financial_year == LATEST)]
        counts = (e.groupby(["diagnosis_group", code_col], observed=True)
                    .size().rename("episodes").reset_index()
                    .rename(columns={code_col: "area_code",
                                     "diagnosis_group": "drug_type"}))
        counts["area_code"] = counts.area_code.astype(str)
        # full cross join so every area has a row for every drug group
        m = areas.merge(pd.DataFrame(
            {"drug_type": e.diagnosis_group.unique()}), how="cross")
        m = m.merge(counts, on=["area_code", "drug_type"], how="left")
        m["episodes"] = m.episodes.fillna(0).astype(int)
        m["rate_per_100k"] = (m.episodes / m.population * 1e5).round(1)
        m["financial_year"] = LATEST
        m.to_csv(f"sa_{level}_map.csv", index=False)
        print(f"Wrote sa_{level}_map.csv ({m.area_code.nunique()} areas)")

        # per-area population group breakdowns for the map click panel
        gg = []
        for col, label in [("sex", "Sex"),
                           ("indigenous_status", "Indigenous status"),
                           ("age_group", "Age group")]:
            t = (e.groupby([code_col, "diagnosis_group", col], observed=True)
                   .size().rename("episodes").reset_index()
                   .rename(columns={code_col: "area_code", col: "level",
                                    "diagnosis_group": "drug_type"}))
            t["dimension"] = label
            gg.append(t)
        g = pd.concat(gg, ignore_index=True)
        g["area_code"] = g.area_code.astype(str)
        g.to_csv(f"sa_{level}_groups.csv", index=False)
        print(f"Wrote sa_{level}_groups.csv")
    else:
        print(f"Skipped sa_{level}_map.csv (run prepare_geodata.py, then "
              "re-run generate_episodes.py and aggregate.py)")
