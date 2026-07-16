# SA Health Statistics Dashboard — Demo v4

**v4:** tab order (Trend · Population groups · Compare regions · Data table · Diagnosis
reference); data currency stamps ("Data as of" = latest discharge date in the data,
"Last refresh" = pipeline run time, written to `data/data_metadata.json` by `aggregate.py`);
official statistical-release design (masthead with provenance chips, SA Health navy/teal,
IBM Plex Mono release stamps, styled metric cards and tabs, footer). **Logo:** drop a
transparent PNG at `streamlit_app/assets/logo.png` (Streamlit) and `shiny_app/www/logo.png`
(Shiny) — apps run fine without one. Every chart also has Plotly's built-in camera icon
(top-right on hover) to download a PNG for reports.

Prototype for **South Australia**, built in both
**R Shiny** and **Python Streamlit** from the same synthetic data pipeline.

**All data are synthetic** (fixed seed 2026). Do not interpret.

## v3 architecture: episode-level pipeline

The data layer now mirrors a real ISAAC extract — unit-record episodes flowing through an
aggregation step, so real data can be dropped in without touching the apps:

```
build_diagnosis_ref.py   ->  diagnosis_ref.csv          (268 ICD-10-AM codes, 15 groups)
generate_episodes.py     ->  sa_aod_episodes.csv        (~68,000 episodes with AdmDateTime,
                                                         DischSummaryDtm, diagnosis_code, ...)
aggregate.py             ->  sa_aod_hospitalisations.csv (published cube: counts, rates, CIs,
                                                         mean bed days)
                         ->  sa_sa3_map.csv / sa_sa2_map.csv (area file for the map; needs geodata)
```

Run everything with one command: `python data/run_pipeline.py`

**Bed days** follow the AIHW convention: discharge date minus admission date, with same-day
episodes counted as **1 patient day**; reported as mean bed days per episode (third Measure option).

**Drug groups** are driven by the Diagnosis Reference Table (15 groups + 'All drug-related'):
Alcohol, Anaesthetics, Analeptics and opioid receptor antagonists, Androgens and anabolic
congeners, Cannabinoids, Hallucinogens, Inhalants, Multiple drug use, Non-opioid analgesic and
antirheumatic, Opioid, Psychostimulants, Psychotropics, Sedative-hypnotics/antiepileptics/
antiparkinson, Steroids or hormones, Other. Adding a category is a CSV edit, not a code change.
The full code list is browsable/searchable in the **Diagnosis reference** tab beside the Data table.

## Dashboard features

- Trend / Compare regions / Population groups (sex, age, Indigenous status, SEIFA, remoteness) /
  Data table / Diagnosis reference tabs, with line/bar/pie chart toggles
- Multi-LHN trend overlay; 'South Australia (All LHNs)' always shown as a dashed reference
- **Map docked as a right side panel** (toggle in sidebar; SA3 default, SA2 switch). Hover shows:
  area name, respective SA2/SA3 code, Total {selected drug group} Episodes, area population
  (latest year), rate per 100k (latest year), and SEIFA quintile details
- Auto-generated **Commentary** (with small-cell guards — rare groups show 'not reportable')
  and technical **Notes**
- Small cells occur naturally in rare groups (e.g. Steroids or hormones) — useful for
  demonstrating suppression rules to supervisors

## Run locally

```bash
cd streamlit_app && pip install -r requirements.txt && streamlit run streamlit_app.py
```
```r
# from shiny_app/ : source("install_packages.R"); shiny::runApp()
```

## Enabling the map (one-off)

1. Download the SA3 (and/or SA2) **shapefile** from the
   [ABS digital boundary files](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files).
2. From `data/`:
   ```bash
   pip install geopandas
   python prepare_geodata.py --shp /path/to/SA3_2021_AUST_GDA2020.shp --level sa3
   python generate_episodes.py    # episodes now carry real SA3 codes
   python aggregate.py            # writes sa_sa3_map.csv
   ```
   Boundaries are filtered to SA, simplified, and re-keyed so app joins can never mismatch.
   Episode SEIFA quintile and remoteness are then **derived from the area of residence**
   (as in reality) rather than sampled independently. Until this is run, the map panel
   shows these instructions instead of erroring.

## Deployment

- **Streamlit Community Cloud** (free): push the repo to GitHub -> share.streamlit.io ->
  point at `streamlit_app/streamlit_app.py`. Deploy the whole repo (apps read `../data/`).
- **shinyapps.io** (free tier): `rsconnect::deployApp("shiny_app")` — copy `data/` contents
  into the app folder first or adjust paths, since only the app directory is bundled.

## Extension roadmap

Schema is indicator-agnostic. Chronic disease PPH and obesity/tobacco PPH dashboards = new
reference table (AIHW PPH condition groupings) + episode extract; apps unchanged. For production:
real ERP/IRSD/remoteness lookups, true age-standardisation (2001 standard population),
<5 cell suppression, and ACCD ICD-10-AM tabular-list wording in the reference table.
