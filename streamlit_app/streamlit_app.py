"""
SA Health Statistics — Alcohol and other drug-related hospitalisations (DEMO v3)
100% SYNTHETIC DATA. Run:  streamlit run streamlit_app.py

v3: episode-derived data (AdmDateTime/DischSummaryDtm); mean bed days measure
(AIHW convention: same-day = 1 day); 15 diagnosis groups + All drug-related
driven by diagnosis_ref.csv; Diagnosis reference tab; map docked as a right
side panel (SA3 default, SA2 toggle) with the specified hover content.
"""

import base64
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

SA_BLUE, SA_TEAL, SA_GREY = "#00539f", "#00a9a5", "#5b6770"
PALETTE = [SA_BLUE, SA_TEAL, "#e57200", "#7ab800", "#8f3f97",
           "#c60c30", "#00778b", "#d0d0ce", "#5b6770", "#f2a900"]
LATEST, FIRST = "2024-25", "2020-21"
STATE = "South Australia (All LHNs)"
ALLDRUG = "All drug-related"
DATA_DIR = Path(__file__).parent.parent / "data"

MEASURES = {"Rate per 100,000 population": ("rate_per_100k", "Rate per 100,000"),
            "Number of hospitalisations": ("count", "Hospitalisations"),
            "Mean length of stay (bed days)": ("mean_bed_days",
                                               "Mean bed days")}

st.set_page_config(page_title="SA AOD hospitalisations (demo)",
                   page_icon="📊", layout="wide")


@st.cache_data
def load(name, **kw):
    p = DATA_DIR / name
    return pd.read_csv(p, **kw) if p.exists() else None


dat = load("sa_aod_hospitalisations.csv")
ref = load("diagnosis_ref.csv")
lhn_all = [STATE] + sorted(x for x in dat.lhn.unique() if x != STATE)
drug_all = [ALLDRUG] + sorted(x for x in dat.drug_type.unique() if x != ALLDRUG)

META_P = DATA_DIR / "data_metadata.json"
META = (json.loads(META_P.read_text()) if META_P.exists()
        else {"data_as_of": "n/a", "last_refresh": "n/a", "version": "v4"})
LOGO = Path(__file__).parent / "assets" / "logo.png"
LOGO_B64 = (base64.b64encode(LOGO.read_bytes()).decode()
            if LOGO.exists() else None)

# ---- Design system (v4): official statistical-release look ---------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@500&display=swap');

html, body, [class*="css"] { font-family: 'Public Sans', sans-serif; }
.stApp { background: #f6f8fa; }
h1, h2, h3 { font-family: 'Archivo', sans-serif; letter-spacing: -0.01em; }

.masthead { background: linear-gradient(100deg, #003a70 0%, #00539f 70%, #006ba6 100%);
  border-radius: 14px; padding: 28px 26px 24px 26px; margin-bottom: 14px;
  border-bottom: 4px solid #00a9a5; display: flex; justify-content: space-between; align-items: center; gap: 18px; }
.masthead .mh-logo { height: 120px; border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.35); flex-shrink: 0; }
.masthead .eyebrow { color: #9fd9d7; font-family: 'IBM Plex Mono', monospace;
  font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; }
.masthead h1 { color: #ffffff; font-size: 1.55rem; margin: 2px 0 10px 0; }
.chip { display: inline-block; font-family: 'IBM Plex Mono', monospace;
  font-size: 0.70rem; padding: 3px 10px; border-radius: 999px;
  margin-right: 8px; background: rgba(255,255,255,0.12); color: #e8f1f8;
  border: 1px solid rgba(255,255,255,0.25); }
.chip-demo { background: #e57200; border-color: #e57200; color: #fff;
  font-weight: 600; }

[data-testid="stMetric"] { background: #ffffff; border: 1px solid #e3e8ee;
  border-left: 4px solid #00539f; border-radius: 10px; padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(16,42,67,0.06); }
[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace;
  color: #00539f; font-size: 1.45rem; }
[data-testid="stMetricLabel"] { color: #5b6770; }

.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 2px solid #e3e8ee; }
.stTabs [data-baseweb="tab"] { font-family: 'Archivo', sans-serif;
  font-weight: 600; color: #5b6770; padding: 8px 14px; }
.stTabs [aria-selected="true"] { color: #00539f;
  border-bottom: 3px solid #00a9a5; }

.footer { color: #5b6770; font-size: 0.75rem; text-align: center;
  padding: 18px 0 4px 0; font-family: 'IBM Plex Mono', monospace; }
</style>
""", unsafe_allow_html=True)

def first_or_none(df):
    return df.iloc[0] if len(df) else None


def geo(level):
    gj = DATA_DIR / f"sa_{level}_boundaries.geojson"
    mp = load(f"sa_{level}_map.csv", dtype={"area_code": str})
    return (json.loads(gj.read_text()) if gj.exists() else None), mp


# ---- Sidebar -----------------------------------------------------------------
with st.sidebar:
    st.subheader("Indicator settings")
    drug = st.selectbox("Drug group (per diagnosis reference)", drug_all)
    measure = st.radio("Measure", list(MEASURES))
    lhn = st.selectbox("Location (Local Health Network)", lhn_all)
    extra_lhns = st.multiselect(
        "Add LHNs to trend comparison",
        [x for x in lhn_all if x not in (lhn, STATE)],
        help=f"'{STATE}' is always shown for reference.")
    show_ci = st.checkbox("Show 95% confidence intervals", True)
    show_map = st.checkbox("Show map side panel", True)
    st.caption("DEMO — synthetic data for prototyping only. "
               "Not actual SA hospitalisation statistics.")
    if not LOGO.exists():
        st.caption("Add your logo at `streamlit_app/assets/logo.png` "
                   "to brand the app.")

ycol, ylab = MEASURES[measure]
is_rate = ycol == "rate_per_100k"

totals = dat[dat.group_by == "Total"]
trend_lhns = list(dict.fromkeys([STATE, lhn] + extra_lhns))
trend = totals[(totals.drug_type == drug) &
               (totals.lhn.isin(trend_lhns))].sort_values("year_start")
sel = trend[trend.lhn == lhn]
row_latest = first_or_none(sel[sel.financial_year == LATEST])
row_first = first_or_none(sel[sel.financial_year == FIRST])


logo_html = (f'<img class="mh-logo" src="data:image/png;base64,{LOGO_B64}">'
             if LOGO_B64 else "")
st.markdown(f"""
<div class="masthead">
  <div>
    <div class="eyebrow">SA Health Statistics · Preventive Health SA (demo)</div>
    <h1>Alcohol and other drug-related hospitalisations</h1>
    <span class="chip chip-demo">DEMO · SYNTHETIC DATA</span>
    <span class="chip">Data as of {META['data_as_of']}</span>
    <span class="chip">Last refresh: {META['last_refresh']}</span>
    <span class="chip">{drug} · {lhn}</span>
  </div>
  {logo_html}
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric(f"Latest year ({LATEST})",
          f"{row_latest[ycol]:,.2f}".rstrip("0").rstrip(".")
          + (" /100k" if is_rate else "")
          if row_latest is not None else "n.p.")
c2.metric(f"Change vs {FIRST}",
          f"{(row_latest[ycol] / row_first[ycol] - 1) * 100:+.0f}%"
          if row_latest is not None and row_first is not None
          and row_first[ycol] else "n.p.")
c3.metric(f"Mean bed days, {LATEST}"
          if ycol != "mean_bed_days" else f"Hospitalisations, {LATEST}",
          (f"{row_latest.mean_bed_days:.2f}" if ycol != "mean_bed_days"
           else f"{row_latest['count']:,}")
          if row_latest is not None else "n.p.")

left, right = st.columns([0.63, 0.37], gap="medium") if show_map \
    else (st.container(), None)

with left:
    tab_trend, tab_strat, tab_reg, tab_table, tab_ref = st.tabs(
        ["Trend", "Population groups", "Compare regions",
         "Data table", "Diagnosis reference"])

    # ---- Trend ----------------------------------------------------------------
    with tab_trend:
        ctype = st.radio("Chart type", ["Line", "Bar"], horizontal=True,
                         key="ct_trend")
        fig = go.Figure()
        for i, l in enumerate(trend_lhns):
            d = trend[trend.lhn == l]
            colr = PALETTE[i % len(PALETTE)]
            if ctype == "Line":
                if show_ci and is_rate and l == lhn:
                    fig.add_trace(go.Scatter(x=d.financial_year, y=d.rate_ucl,
                                             line=dict(width=0),
                                             hoverinfo="skip",
                                             showlegend=False))
                    fig.add_trace(go.Scatter(x=d.financial_year, y=d.rate_lcl,
                                             fill="tonexty",
                                             fillcolor="rgba(0,83,159,0.12)",
                                             line=dict(width=0),
                                             hoverinfo="skip",
                                             showlegend=False))
                fig.add_trace(go.Scatter(
                    x=d.financial_year, y=d[ycol], mode="lines+markers",
                    name=l, line=dict(color=colr, width=3,
                                      dash="dash" if l == STATE else "solid"),
                    marker=dict(size=7)))
            else:
                fig.add_trace(go.Bar(x=d.financial_year, y=d[ycol], name=l,
                                     marker_color=colr))
        fig.update_layout(xaxis_title="Financial year", yaxis_title=ylab,
                          yaxis_rangemode="tozero", hovermode="x unified",
                          barmode="group", height=430, margin=dict(t=25),
                          legend=dict(orientation="h", y=-0.28))
        st.plotly_chart(fig, use_container_width=True)

    # ---- Regions ---------------------------------------------------------------
    with tab_reg:
        ctype = st.radio("Chart type", ["Bar", "Pie"], horizontal=True,
                         key="ct_reg")
        reg = totals[(totals.drug_type == drug) &
                     (totals.financial_year == LATEST) &
                     (totals.lhn != STATE)].sort_values(ycol)
        hi_colors = [SA_BLUE if l == lhn else SA_TEAL for l in reg.lhn]
        if ctype == "Bar":
            fig = go.Figure(go.Bar(
                x=reg[ycol], y=reg.lhn, orientation="h",
                marker_color=hi_colors,
                error_x=dict(array=reg.rate_ucl - reg.rate_per_100k,
                             arrayminus=reg.rate_per_100k - reg.rate_lcl,
                             color=SA_GREY)
                if (is_rate and show_ci) else None))
            sa_row = first_or_none(
                totals[(totals.drug_type == drug) &
                       (totals.financial_year == LATEST) &
                       (totals.lhn == STATE)])
            if is_rate and sa_row is not None:
                fig.add_vline(x=sa_row[ycol], line_dash="dash",
                              line_color=SA_BLUE, annotation_text="SA average",
                              annotation_font_color=SA_BLUE)
            fig.update_layout(xaxis_title=ylab,
                              title=f"Local Health Networks, {LATEST} — {ylab}")
        else:
            fig = go.Figure(go.Pie(
                labels=reg.lhn, values=reg[ycol],
                pull=[0.12 if l == lhn else 0 for l in reg.lhn],
                marker=dict(colors=PALETTE,
                            line=dict(color="white", width=1))))
            fig.update_layout(title=f"Share of {ylab.lower()} by LHN, "
                                    f"{LATEST} (selected LHN pulled out)")
        fig.update_layout(height=470, margin=dict(t=45))
        st.plotly_chart(fig, use_container_width=True)

    # ---- Population groups: all breakdowns at once -------------------------------
    with tab_strat:
        ctype = st.radio("Chart type", ["Bar", "Line (trend by group)", "Pie"],
                         horizontal=True, key="ct_strat")
        st.caption(f"All population group breakdowns — {drug}, {lhn}, "
                   f"{ylab.lower()}" +
                   (f", {LATEST}" if not ctype.startswith("Line") else ""))
        SHORT = {"Q1 - most disadvantaged": "Q1",
                 "Q5 - least disadvantaged": "Q5",
                 "Major Cities of Australia": "Major Cities",
                 "Inner Regional Australia": "Inner Regional",
                 "Outer Regional Australia": "Outer Regional",
                 "Remote Australia": "Remote",
                 "Very Remote Australia": "Very Remote"}
        STRATS = [("Sex", "sex"), ("Age group", "age_group"),
                  ("Indigenous status", "indigenous_status"),
                  ("SEIFA quintile", "seifa_quintile"),
                  ("Remoteness", "remoteness")]

        def strat_fig(strat, col):
            sd = dat[(dat.group_by == strat) & (dat.drug_type == drug) &
                     (dat.lhn == lhn)].copy()
            sd["label"] = sd[col].map(lambda x: SHORT.get(x, x))
            order = [SHORT.get(x, x) for x in sorted(sd[col].unique())]
            latest_sd = sd[sd.financial_year == LATEST]
            if ctype == "Bar":
                f = go.Figure(go.Bar(
                    x=latest_sd.label, y=latest_sd[ycol],
                    marker_color=SA_TEAL,
                    error_y=dict(
                        array=latest_sd.rate_ucl - latest_sd.rate_per_100k,
                        arrayminus=(latest_sd.rate_per_100k
                                    - latest_sd.rate_lcl),
                        color=SA_GREY) if (is_rate and show_ci) else None))
                f.update_xaxes(categoryorder="array", categoryarray=order)
            elif ctype.startswith("Line"):
                f = go.Figure()
                for i, lev in enumerate(order):
                    d = sd[sd.label == lev].sort_values("year_start")
                    f.add_trace(go.Scatter(
                        x=d.financial_year, y=d[ycol], mode="lines+markers",
                        name=lev, marker=dict(size=5),
                        line=dict(color=PALETTE[i % len(PALETTE)], width=2)))
                f.update_layout(hovermode="x unified")
            else:
                f = go.Figure(go.Pie(
                    labels=latest_sd.label, values=latest_sd[ycol],
                    marker=dict(colors=PALETTE,
                                line=dict(color="white", width=1)),
                    textinfo="label+percent"))
            f.update_layout(
                title=dict(text=strat, font=dict(size=15)), height=300,
                margin=dict(l=10, r=10, t=40, b=10), showlegend=(
                    ctype.startswith("Line")),
                legend=dict(font=dict(size=10), orientation="h", y=-0.25))
            return f

        for row in (STRATS[:2], STRATS[2:4], STRATS[4:]):
            cols = st.columns(len(row))
            for c, (strat, col) in zip(cols, row):
                with c:
                    st.plotly_chart(strat_fig(strat, col),
                                    use_container_width=True,
                                    key=f"strat_{col}_{ctype}")

    # ---- Data table -----------------------------------------------------------------
    with tab_table:
        show = dat[(dat.drug_type == drug) & (dat.lhn == lhn)]
        st.dataframe(show.drop(columns=["indicator"]),
                     use_container_width=True, hide_index=True, height=400)
        st.download_button("Download data (CSV)",
                           show.to_csv(index=False).encode(),
                           file_name="sa_aod_selection.csv", mime="text/csv")

    # ---- Diagnosis reference ----------------------------------------------------------
    with tab_ref:
        st.markdown("**Diagnosis Reference Table** — ICD-10-AM codes "
                    "defining each drug group (drives the Drug group filter).")
        q = st.text_input("Search code, description, or group",
                          placeholder="e.g. F15, cocaine, Opioid")
        r = ref.rename(columns={
            "diagnosis_code": "Diagnosis Code",
            "diagnosis_description": "Diagnosis Description",
            "diagnosis_group": "Diagnosis Description Group"})
        if q:
            mask = r.apply(lambda c: c.astype(str)
                           .str.contains(q, case=False)).any(axis=1)
            r = r[mask]
        st.dataframe(r, use_container_width=True, hide_index=True, height=420)
        st.download_button("Download reference table (CSV)",
                           ref.to_csv(index=False).encode(),
                           file_name="diagnosis_ref.csv", mime="text/csv")

# ---- Map side panel -----------------------------------------------------------
if show_map:
    with right:
        lvl = st.radio("Geography", ["SA3", "SA2"], horizontal=True,
                       key="map_lvl").lower()
        geojson, mp = geo(lvl)
        if geojson is None or mp is None:
            st.info(
                f"**{lvl.upper()} map not available yet.** Download the ABS "
                f"ASGS Ed 3 (2021) {lvl.upper()} shapefile, then run in "
                "`data/`:\n\n"
                f"```\npython prepare_geodata.py --shp <path> --level {lvl}\n"
                "python generate_episodes.py\npython aggregate.py\n```")
            st.link_button(
                "ABS digital boundary files",
                "https://www.abs.gov.au/statistics/standards/"
                "australian-statistical-geography-standard-asgs-edition-3/"
                "jul2021-jun2026/access-and-downloads/digital-boundary-files")
        else:
            m = mp[mp.drug_type == drug]
            LVL = lvl.upper()
            fig = go.Figure(go.Choroplethmap(
                geojson=geojson, locations=m.area_code,
                featureidkey="properties.area_code", z=m.rate_per_100k,
                colorscale="YlGnBu", marker_line_color="white",
                marker_line_width=0.5,
                colorbar=dict(title="Rate /100k", x=0.02, len=0.5),
                customdata=m[["episodes", "population", "rate_per_100k",
                              "seifa_quintile", "area_name"]],
                hovertemplate=(
                    "<b>%{customdata[4]}</b><br>"
                    f"Respective {LVL} code: " + "%{location}<br>"
                    f"Total {drug} Episodes: " + "%{customdata[0]:,}<br>"
                    f"{LVL} Population ({LATEST}): " + "%{customdata[1]:,}<br>"
                    f"Rate per 100k ({LATEST}): " + "%{customdata[2]:.1f}<br>"
                    "Quintile Details: %{customdata[3]}<extra></extra>")))
            fig.update_layout(
                map=dict(style="carto-positron",
                         center=dict(lat=-34.9, lon=138.6), zoom=4.6),
                height=460, margin=dict(l=0, r=0, t=25, b=0),
                clickmode="event+select",
                title=dict(text=f"{drug}, {LATEST}, {lvl.upper()}",
                           font=dict(size=15)))
            event = st.plotly_chart(fig, use_container_width=True,
                                    on_select="rerun",
                                    selection_mode="points",
                                    key=f"map_{lvl}")
            st.caption("Hover an area for details; **click** an area for its "
                       "population group breakdown.")

            # -- clicked area (or selectbox fallback) -> detail panel --------
            clicked = None
            try:
                pts = event.selection.points
                if pts:
                    clicked = str(pts[0].get("location") or "")
            except (AttributeError, TypeError):
                pass
            name_by_code = dict(zip(m.area_code, m.area_name))
            opts = ["—"] + sorted(m.area_name.unique())
            pick = st.selectbox("...or select an area", opts,
                                key=f"pick_{lvl}")
            if not clicked and pick != "—":
                clicked = m[m.area_name == pick].area_code.iloc[0]

            grp = load(f"sa_{lvl}_groups.csv", dtype={"area_code": str})
            if clicked and clicked in name_by_code:
                info = m[m.area_code == clicked].iloc[0]
                st.markdown(
                    f"##### {info.area_name} ({lvl.upper()} {clicked})\n"
                    f"**SEIFA Score:** {info.seifa_quintile} · "
                    f"**Remoteness:** {info.remoteness}\n\n"
                    f"{drug}, {LATEST}: **{info.episodes:,} episodes**, "
                    f"rate **{info.rate_per_100k:,.1f}** per 100,000")
                if grp is not None:
                    sub = grp[(grp.area_code == clicked) &
                              (grp.drug_type == drug)]
                    for dim in ["Sex", "Indigenous status", "Age group"]:
                        d = sub[sub.dimension == dim].sort_values("level")
                        if not len(d):
                            continue
                        f = go.Figure(go.Bar(
                            x=d.episodes, y=d.level, orientation="h",
                            marker_color=SA_TEAL,
                            text=d.episodes, textposition="outside"))
                        f.update_layout(
                            title=dict(text=f"{dim} (episodes)",
                                       font=dict(size=13)),
                            height=60 + 32 * len(d),
                            margin=dict(l=10, r=25, t=30, b=5),
                            xaxis=dict(visible=False),
                            yaxis=dict(tickfont=dict(size=12)))
                        st.plotly_chart(f, use_container_width=True,
                                        key=f"det_{lvl}_{dim}")
                    st.caption("Small counts would be suppressed (n < 5) in "
                               "production.")

# ---- Commentary + Notes -----------------------------------------------------------
st.divider()
with st.expander("**Commentary — what can we learn from this data?**",
                 expanded=True):
    if row_latest is None or row_first is None or not row_first.rate_per_100k:
        st.markdown(f"Counts for **{drug}** in {lhn} are too small to report "
                    "reliably for one or both comparison years (in production "
                    "these cells would be suppressed, n < 5). Select a larger "
                    "group or region for commentary.")
    else:
        chg = (row_latest.rate_per_100k / row_first.rate_per_100k - 1) * 100
        dirn = ("increased" if chg > 3 else "decreased" if chg < -3
                else "remained relatively stable")
        reg = totals[(totals.drug_type == drug) &
                     (totals.financial_year == LATEST) &
                     (totals.lhn != STATE) & (totals["count"] >= 5)]
        hi = reg.loc[reg.rate_per_100k.idxmax()] if len(reg) else None
        lo = reg.loc[reg.rate_per_100k.idxmin()] if len(reg) else None

        def ratio(grp, col, num, den):
            d = dat[(dat.group_by == grp) & (dat.drug_type == drug) &
                    (dat.lhn == STATE) & (dat.financial_year == LATEST)]
            n = d[d[col] == num]
            dn = d[d[col] == den]
            if len(n) and len(dn) and dn.rate_per_100k.iloc[0] > 0 \
                    and n["count"].iloc[0] >= 5:
                return n.rate_per_100k.iloc[0] / dn.rate_per_100k.iloc[0]
            return None

        r_ind = ratio("Indigenous status", "indigenous_status",
                      "First Nations", "Non-Indigenous")
        r_sei = ratio("SEIFA quintile", "seifa_quintile",
                      "Q1 - most disadvantaged", "Q5 - least disadvantaged")
        r_rem = ratio("Remoteness", "remoteness",
                      "Very Remote Australia", "Major Cities of Australia")
        fmt = lambda r, s: (f"**{r:.1f} times higher {s}**" if r
                            else f"not reportable {s} (small numbers)")
        parts = [
            f"In {lhn}, the age-standardised rate of {drug.lower()} "
            f"hospitalisations **{dirn} by {chg:+.0f}%** between {FIRST} and "
            f"{LATEST} ({row_first.rate_per_100k:,.1f} to "
            f"{row_latest.rate_per_100k:,.1f} per 100,000). Episodes in this "
            f"group averaged **{row_latest.mean_bed_days:.1f} bed days** in "
            f"{LATEST} (same-day episodes counted as one day)."]
        if hi is not None and lo is not None and lo.rate_per_100k > 0:
            parts.append(
                f"Across Local Health Networks in {LATEST}, rates were "
                f"highest in **{hi.lhn}** ({hi.rate_per_100k:,.1f}) and "
                f"lowest in **{lo.lhn}** ({lo.rate_per_100k:,.1f}) — a "
                f"{hi.rate_per_100k / lo.rate_per_100k:.1f}-fold difference.")
        parts.append(
            "Statewide, hospitalisation rates were "
            + fmt(r_ind, "for First Nations people than non-Indigenous people")
            + ", " + fmt(r_sei, "in the most disadvantaged SEIFA quintile "
                                "(Q1) than the least disadvantaged (Q5)")
            + ", and " + fmt(r_rem, "in Very Remote areas than Major Cities")
            + ". Persistent socioeconomic and geographic gradients suggest "
              "prevention effort should be weighted toward disadvantaged and "
              "remote communities.")
        parts.append("*Commentary is generated automatically from the current "
                     "selection — synthetic data, do not interpret.*")
        st.markdown("\n\n".join(parts))

with st.expander("**Notes — technical details of this data**"):
    st.markdown(f"""
- **Source (intended):** SA admitted patient activity data (ISAAC); this demo
  uses synthetic unit-record episodes generated by `data/generate_episodes.py`
  (seed 2026) and aggregated by `data/aggregate.py`.
- **Indicator definition:** episodes with a principal diagnosis mapped to one
  of 15 drug groups via the Diagnosis Reference Table (see tab); 'All
  drug-related' is the union of all groups.
- **Bed days:** date of discharge (`DischSummaryDtm`) minus date of admission
  (`AdmDateTime`), with same-day episodes counted as **1 patient day** (AIHW
  convention); reported as the mean per episode.
- **Rates:** directly age-standardised to the 2001 Australian standard
  population (label only in this demo), per 100,000; 95% CIs assume Poisson
  counts.
- **Geography:** LHNs per SA Health; SA2/SA3 per ABS ASGS Ed 3 (2021);
  Remoteness per ASGS Remoteness Structure; SEIFA quintiles per ABS IRSD.
- **Indigenous status** as recorded at admission; subject to
  under-identification.
- **Diagnosis descriptions** are generated from standard ICD-10 category
  wording; fifth-character (ICD-10-AM) subdivisions are labelled generically —
  replace with ACCD ICD-10-AM tabular list wording for production.
- **Suppression (production rule):** counts under 5 suppressed ('n.p.');
  rates on counts under 20 flagged as unstable.
- **Reporting period:** financial years {FIRST} to {LATEST}.
""")

st.markdown(
    f"""<div class="footer">SA AOD hospitalisations dashboard
    {META.get("version", "v4")} · reporting period
    {META.get("reporting_period", "")} · data as of {META["data_as_of"]} ·
    last refresh {META["last_refresh"]} · synthetic demonstration data</div>""",
    unsafe_allow_html=True)
