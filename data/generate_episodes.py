"""
Generate synthetic UNIT-RECORD hospitalisation episodes (v3).

One row per episode, structurally matching an ISAAC-style extract:
  episode_id, AdmDateTime, DischSummaryDtm, diagnosis_code (ICD-10-AM,
  sampled from diagnosis_ref.csv), lhn, sex, age_group, indigenous_status,
  seifa_quintile, remoteness, sa3_code/sa2_code (if geodata prepared).

Bed days are NOT stored — they are derived downstream in aggregate.py using
the AIHW convention. 100% SYNTHETIC.

Run:  python build_diagnosis_ref.py   (first)
      python generate_episodes.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)

YEARS = list(range(2020, 2025))                 # FY start years: 2020-21..2024-25
BASE_EPISODES = 13_000                          # statewide, first year
ANNUAL_GROWTH = 1.03

GROUP_SHARE = {                                 # share of episodes, LOS mean (days)
    "Alcohol": (0.45, 3.2), "Psychostimulants": (0.15, 2.4),
    "Opioid": (0.08, 2.8), "Cannabinoids": (0.08, 1.8),
    "Multiple drug use": (0.07, 3.0),
    "Sedative-hypnotics, antiepileptics and antiparkinson": (0.06, 2.2),
    "Psychotropics (antidepressants, antipsychotics and neuroleptics)": (0.04, 2.0),
    "Non-opioid analgesic and antirheumatic": (0.03, 1.5),
    "Hallucinogens": (0.010, 1.5), "Other": (0.012, 2.0),
    "Inhalants": (0.007, 1.8), "Anaesthetics": (0.005, 1.5),
    "Analeptics and opioid receptor antagonists": (0.003, 1.6),
    "Androgens and anabolic congeners": (0.002, 1.4),
    "Steroids or hormones": (0.001, 1.4),
}

LHNS = {"Central Adelaide LHN": (490_000, 1.10),
        "Northern Adelaide LHN": (420_000, 1.20),
        "Southern Adelaide LHN": (400_000, 0.95),
        "Barossa Hills Fleurieu LHN": (165_000, 0.80),
        "Eyre and Far North LHN": (55_000, 1.30),
        "Flinders and Upper North LHN": (70_000, 1.35),
        "Limestone Coast LHN": (65_000, 0.90),
        "Riverland Mallee Coorong LHN": (70_000, 1.05),
        "Yorke and Northern LHN": (75_000, 0.95)}

AGE = {"0-14": (0.05, 0.18), "15-24": (1.60, 0.12), "25-34": (1.90, 0.14),
       "35-44": (1.55, 0.13), "45-54": (1.10, 0.13), "55-64": (0.70, 0.12),
       "65+": (0.40, 0.18)}
SEIFA = {"Q1 - most disadvantaged": (1.80, 0.20), "Q2": (1.30, 0.20),
         "Q3": (1.00, 0.20), "Q4": (0.80, 0.20),
         "Q5 - least disadvantaged": (0.60, 0.20)}
REMOTE = {"Major Cities of Australia": (0.95, 0.74),
          "Inner Regional Australia": (1.05, 0.12),
          "Outer Regional Australia": (1.35, 0.10),
          "Remote Australia": (1.80, 0.03),
          "Very Remote Australia": (2.40, 0.01)}


def weighted(d):
    keys = list(d)
    w = np.array([m * s for m, s in d.values()])
    return keys, w / w.sum()


ref = pd.read_csv("diagnosis_ref.csv")
codes_by_group = ref.groupby("diagnosis_group")["diagnosis_code"].apply(list)

# Optional geography (run prepare_geodata.py first to enable the map)
areas = {}
for level in ("sa3", "sa2"):
    p = Path(f"sa_{level}_areas.csv")
    if p.exists():
        a = pd.read_csv(p, dtype={"area_code": str})
        areas[level] = (a, a.population / a.population.sum())
        print(f"Geography enabled: sampling {level.upper()} codes "
              f"({len(a)} areas)")

lhn_keys, lhn_p = weighted(LHNS)
age_keys, age_p = weighted(AGE)
sei_keys, sei_p = weighted(SEIFA)
rem_keys, rem_p = weighted(REMOTE)
grp_keys = list(GROUP_SHARE)
grp_p = np.array([s for s, _ in GROUP_SHARE.values()])
grp_p = grp_p / grp_p.sum()
los_mean = {g: m for g, (_, m) in GROUP_SHARE.items()}

rows = []
eid = 100_000
for i, y in enumerate(YEARS):
    n = int(BASE_EPISODES * ANNUAL_GROWTH ** i * (0.92 if y == 2020 else 1))
    fy_start = pd.Timestamp(f"{y}-07-01")
    for _ in range(n):
        eid += 1
        g = rng.choice(grp_keys, p=grp_p)
        adm = (fy_start + pd.Timedelta(days=int(rng.uniform(0, 365)),
                                       hours=int(rng.uniform(0, 24)),
                                       minutes=int(rng.uniform(0, 60))))
        same_day = rng.random() < 0.35
        los_days = 0 if same_day else max(
            1, int(rng.lognormal(np.log(los_mean[g]), 0.8)))
        disch = adm + pd.Timedelta(days=los_days,
                                   hours=int(rng.uniform(1, 10)) if same_day
                                   else int(rng.uniform(-6, 6)))
        if disch <= adm:
            disch = adm + pd.Timedelta(hours=4)
        row = dict(
            episode_id=f"EP{eid}",
            AdmDateTime=adm.strftime("%Y-%m-%d %H:%M"),
            DischSummaryDtm=disch.strftime("%Y-%m-%d %H:%M"),
            financial_year=f"{y}-{str(y + 1)[2:]}", year_start=y,
            diagnosis_code=rng.choice(codes_by_group[g]),
            lhn=rng.choice(lhn_keys, p=lhn_p),
            sex="Males" if rng.random() < 0.62 else "Females",
            age_group=rng.choice(age_keys, p=age_p),
            indigenous_status=("First Nations" if rng.random() < 0.082
                               else "Non-Indigenous"),
        )
        for level, (a, pw) in areas.items():
            j = rng.choice(len(a), p=pw)
            row[f"{level}_code"] = a.area_code.iloc[j]
            if level == "sa3":                       # derive from area
                row["seifa_quintile"] = a.seifa_quintile.iloc[j]
                row["remoteness"] = a.remoteness.iloc[j]
        if "seifa_quintile" not in row:              # no geodata yet: sample
            row["seifa_quintile"] = rng.choice(sei_keys, p=sei_p)
            row["remoteness"] = rng.choice(rem_keys, p=rem_p)
        rows.append(row)

df = pd.DataFrame(rows)
df.to_csv("sa_aod_episodes.csv", index=False)
print(f"Wrote sa_aod_episodes.csv: {len(df):,} episodes, "
      f"{df.diagnosis_code.nunique()} distinct ICD-10-AM codes")
