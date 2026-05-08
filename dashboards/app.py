"""Energy Intelligence Dashboard — Streamlit app.

Connects directly to Snowflake and renders interactive charts for energy
access gap analysis across the Global South.

Run locally:  streamlit run dashboards/app.py
Docker:       make up  →  http://localhost:8501
"""

import json
import os

import pandas as pd
import plotly.express as px
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Energy Intelligence",
    page_icon="⚡",
    layout="wide",
)


# ── Snowflake ─────────────────────────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def _conn():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database=os.environ.get("SNOWFLAKE_DATABASE", "ENERGY_INTELLIGENCE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "ENERGY_WH"),
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        schema="STAGING_MARTS",
    )


@st.cache_data(ttl=600, show_spinner=False)
def _query(sql: str) -> pd.DataFrame:
    cur = _conn().cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)


# ── Lightweight bootstrap queries (run once, tiny) ────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def _available_years() -> list[int]:
    df = _query("SELECT DISTINCT YEAR FROM MART_ENERGY_ACCESS_SUMMARY ORDER BY YEAR DESC")
    return df["YEAR"].tolist()


@st.cache_data(ttl=600, show_spinner=False)
def _available_countries() -> list[str]:
    df = _query("SELECT DISTINCT COUNTRY_CODE FROM MART_ENERGY_ACCESS_SUMMARY ORDER BY COUNTRY_CODE")
    return df["COUNTRY_CODE"].tolist()


# ── Per-year data queries (cached per year, run after sidebar) ────────────────

@st.cache_data(ttl=600, show_spinner="Loading summary data…")
def _summary(year: int) -> pd.DataFrame:
    return _query(f"""
        SELECT COUNTRY_CODE, COUNTRY_NAME, ADMIN_NAME, YEAR,
               ELECTRICITY_ACCESS_PCT, MEAN_NIGHTLIGHT_RADIANCE,
               DIST_TO_GRID_KM, TOTAL_POPULATION, POP_DENSITY_KM2,
               ENERGY_ACCESS_SCORE, SCORE_TIER,
               NIGHTLIGHT_CATEGORY, POPULATION_CATEGORY, GRID_PROXIMITY_CATEGORY
        FROM MART_ENERGY_ACCESS_SUMMARY
        WHERE YEAR = {year}
    """)


@st.cache_data(ttl=600, show_spinner="Loading KPI data…")
def _kpi(year: int) -> pd.DataFrame:
    return _query(f"""
        SELECT COUNTRY_CODE, YEAR, ELECTRICITY_ACCESS_PCT,
               TOTAL_POPULATION, POP_WITHOUT_ELECTRICITY,
               MEAN_NIGHTLIGHT_RADIANCE, N_POWER_PLANTS,
               INSTALLED_CAPACITY_MW, N_CRITICAL_ZONES
        FROM MART_COUNTRY_KPI
        WHERE YEAR = {year}
    """)


@st.cache_data(ttl=600, show_spinner="Loading map geometry…")
def _geo(year: int) -> pd.DataFrame:
    return _query(f"""
        SELECT COUNTRY_CODE, ADMIN_NAME, ENERGY_ACCESS_SCORE, SCORE_TIER,
               GEOMETRY_JSON
        FROM MART_ENERGY_ACCESS_SUMMARY
        WHERE YEAR = {year} AND GEOMETRY_JSON IS NOT NULL
    """)


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("⚡ Energy Intelligence")
st.sidebar.markdown("---")

all_years = _available_years()
all_countries = _available_countries()

selected_year = st.sidebar.selectbox("Year", all_years, index=0)
selected_countries = st.sidebar.multiselect(
    "Country", all_countries, placeholder="All countries"
)

# ── Load data for selected year ───────────────────────────────────────────────

summary = _summary(selected_year)
kpi     = _kpi(selected_year)
geo     = _geo(selected_year)

if selected_countries:
    summary = summary[summary["COUNTRY_CODE"].isin(selected_countries)]
    kpi     = kpi[kpi["COUNTRY_CODE"].isin(selected_countries)]
    geo     = geo[geo["COUNTRY_CODE"].isin(selected_countries)]

st.sidebar.markdown("---")
st.sidebar.caption(f"{len(summary):,} admin-2 regions  ·  {summary['COUNTRY_CODE'].nunique()} countries")

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Energy Access Intelligence Dashboard")
st.caption(f"Year: **{selected_year}**  ·  Regions: **{len(summary):,}**")

# ── KPI strip ─────────────────────────────────────────────────────────────────

k1, k2, k3, k4 = st.columns(4)
k1.metric("Countries", kpi["COUNTRY_CODE"].nunique())
k2.metric(
    "Avg Energy Access Score",
    f"{summary['ENERGY_ACCESS_SCORE'].mean():.1f}",
    help="0–100 composite, higher = more underserved",
)
k3.metric(
    "Critical Zones",
    f"{int(kpi['N_CRITICAL_ZONES'].sum()):,}",
    help="Admin-2 regions with score ≥ 75",
)
k4.metric(
    "People Without Electricity",
    f"{int(kpi['POP_WITHOUT_ELECTRICITY'].sum() / 1e6):.1f}M",
)

st.markdown("---")

# ── Map: Energy Access Score by Region ────────────────────────────────────────

st.subheader("Energy Access Score by Region")

if geo.empty:
    st.info("No geometry data available for the selected filters.")
else:
    geo_plot = geo.reset_index(drop=True)
    geo_plot["region_id"] = geo_plot.index

    features = []
    for i, row in geo_plot.iterrows():
        coords = json.loads(row["GEOMETRY_JSON"])
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "properties": {"region_id": i},
        })
    geojson = {"type": "FeatureCollection", "features": features}

    fig_map = px.choropleth_mapbox(
        geo_plot,
        geojson=geojson,
        featureidkey="properties.region_id",
        locations="region_id",
        color="ENERGY_ACCESS_SCORE",
        color_continuous_scale="RdYlGn_r",
        range_color=[0, 100],
        mapbox_style="carto-darkmatter",
        zoom=2,
        center={"lat": 5, "lon": 25},
        opacity=0.75,
        hover_name="ADMIN_NAME",
        hover_data={"ENERGY_ACCESS_SCORE": ":.1f", "SCORE_TIER": True, "region_id": False},
        labels={"ENERGY_ACCESS_SCORE": "Score"},
        height=550,
    )
    fig_map.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="Score<br>(0–100)", thickness=14),
    )
    st.plotly_chart(fig_map, width="stretch")
    st.caption("Score 0–100 · higher = more underserved · green → yellow → red")

st.markdown("---")

# ── Row 1: two bar charts ──────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Avg Energy Access Score by Country")
    score_by_country = (
        summary.groupby(["COUNTRY_CODE", "COUNTRY_NAME"], as_index=False)["ENERGY_ACCESS_SCORE"]
        .mean()
        .sort_values(by="ENERGY_ACCESS_SCORE", ascending=False)
    )
    fig = px.bar(
        score_by_country,
        x="COUNTRY_CODE",
        y="ENERGY_ACCESS_SCORE",
        color="ENERGY_ACCESS_SCORE",
        color_continuous_scale="Oranges",
        labels={"COUNTRY_CODE": "Country", "ENERGY_ACCESS_SCORE": "Score (0–100)"},
        hover_data={"COUNTRY_NAME": True},
    )
    fig.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

with col2:
    st.subheader("Electricity Access % by Country")
    elec_by_country = (
        kpi.groupby("COUNTRY_CODE", as_index=False)["ELECTRICITY_ACCESS_PCT"]
        .mean()
        .sort_values(by="ELECTRICITY_ACCESS_PCT", ascending=True)
    )
    fig2 = px.bar(
        elec_by_country,
        x="COUNTRY_CODE",
        y="ELECTRICITY_ACCESS_PCT",
        color="ELECTRICITY_ACCESS_PCT",
        color_continuous_scale="Blues",
        labels={"COUNTRY_CODE": "Country", "ELECTRICITY_ACCESS_PCT": "Access (%)"},
    )
    fig2.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(t=10))
    st.plotly_chart(fig2, width="stretch")

# ── Row 2: pie + bar ───────────────────────────────────────────────────────────

col3, col4 = st.columns(2)

with col3:
    st.subheader("Score Tier Distribution")
    tier_order = ["critical", "high", "medium", "low"]
    tier_colors = {"critical": "#d62728", "high": "#ff7f0e", "medium": "#ffbb78", "low": "#2ca02c"}
    tier_counts = (
        summary["SCORE_TIER"]
        .value_counts()
        .reindex(tier_order)
        .dropna()
        .reset_index()
    )
    tier_counts.columns = ["SCORE_TIER", "COUNT"]
    fig3 = px.pie(
        tier_counts,
        names="SCORE_TIER",
        values="COUNT",
        hole=0.45,
        color="SCORE_TIER",
        color_discrete_map=tier_colors,
    )
    fig3.update_layout(margin=dict(t=10))
    st.plotly_chart(fig3, width="stretch")

with col4:
    st.subheader("Critical Zones by Country")
    critical_by_country = (
        kpi.groupby("COUNTRY_CODE", as_index=False)["N_CRITICAL_ZONES"]
        .sum()
        .sort_values(by="N_CRITICAL_ZONES", ascending=False)
    )
    fig4 = px.bar(
        critical_by_country,
        x="COUNTRY_CODE",
        y="N_CRITICAL_ZONES",
        color="N_CRITICAL_ZONES",
        color_continuous_scale="Reds",
        labels={"COUNTRY_CODE": "Country", "N_CRITICAL_ZONES": "Critical Zones"},
    )
    fig4.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(t=10))
    st.plotly_chart(fig4, width="stretch")

# ── Row 3: worst-25 table ─────────────────────────────────────────────────────

st.markdown("---")
st.subheader("25 Most Underserved Regions")

worst = (
    summary[[
        "COUNTRY_CODE", "ADMIN_NAME", "ENERGY_ACCESS_SCORE", "SCORE_TIER",
        "ELECTRICITY_ACCESS_PCT", "TOTAL_POPULATION", "DIST_TO_GRID_KM",
        "MEAN_NIGHTLIGHT_RADIANCE",
    ]]
    .sort_values("ENERGY_ACCESS_SCORE", ascending=False)
    .head(25)
    .reset_index(drop=True)
)
worst.index += 1

st.dataframe(
    worst,
    width="stretch",
    height=400,
    column_config={
        "ENERGY_ACCESS_SCORE": st.column_config.ProgressColumn(
            "Energy Access Score", min_value=0, max_value=100, format="%.1f"
        ),
        "ELECTRICITY_ACCESS_PCT": st.column_config.NumberColumn(
            "Electricity Access %", format="%.1f%%"
        ),
        "TOTAL_POPULATION": st.column_config.NumberColumn(
            "Population", format="%,d"
        ),
        "DIST_TO_GRID_KM": st.column_config.NumberColumn(
            "Dist to Grid (km)", format="%.1f"
        ),
        "MEAN_NIGHTLIGHT_RADIANCE": st.column_config.NumberColumn(
            "Nightlight Radiance", format="%.3f"
        ),
    },
)
