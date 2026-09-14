"""
Example: Thailand province map showing dominant/selected crop cultivation,
plus a market-analysis section for targeting a new chemical by crop.
Uses apisit/thailand.json (thailandWithName.json) for province boundaries.

Run with: streamlit run thailand_crop_map_example.py
"""

import requests
import pandas as pd
import plotly.express as px
import streamlit as st

GEOJSON_URL = (
    "https://raw.githubusercontent.com/apisit/thailand.json"
    "/master/thailandWithName.json"
)

@st.cache_data
def load_geojson():
    resp = requests.get(GEOJSON_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()

DATA_PATH = "crop_area_by_provinces_TEMPLATE.xlsx"  # your real workbook, same folder as this script

@st.cache_data
def load_crop_data():
    df = pd.read_excel(DATA_PATH, sheet_name="crop_area_by_provinces")
    df = df.rename(columns={"province_name_en": "province"})
    return df[["province", "region", "SHK_region", "crop", "crop_group", "year",
               "area_planted_rai", "area_harvested_rai"]]

def build_name_lookup(geojson):
    """Province names as they appear in the geojson — use this to check
    your crop-data spellings actually match before plotting."""
    return sorted(f["properties"]["name"] for f in geojson["features"])

def render_crop_explorer(df, geojson):
    st.header("Crop Explorer")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        selected_crop = st.selectbox("Select crop", sorted(df["crop"].unique()))
    with col2:
        # Only years that actually exist for THIS crop -- e.g. rice might have
        # 2025 while a fruit crop's latest available data is still 2024.
        years_for_crop = sorted(
            df.loc[df["crop"] == selected_crop, "year"].dropna().unique(), reverse=True
        )
        selected_year = st.selectbox("Year", years_for_crop)
    with col3:
        metric = st.selectbox("Metric", ["area_planted_rai", "area_harvested_rai"])
    with col4:
        shk_options = ["All"] + sorted(df["SHK_region"].dropna().unique())
        selected_shk = st.selectbox("Company sales region (SHK_region)", shk_options)

    filtered = df[(df["crop"] == selected_crop) & (df["year"] == selected_year)]
    if selected_shk != "All":
        filtered = filtered[filtered["SHK_region"] == selected_shk]

    # One value per province for the map (sums duplicate rows if any).
    map_data = filtered.groupby("province", as_index=False)[metric].sum()

    fig = px.choropleth_map(
        map_data,
        geojson=geojson,
        locations="province",
        featureidkey="properties.name",   # <-- the join key
        color=metric,
        color_continuous_scale="Greens",
        map_style="carto-positron",
        zoom=4.5,
        center={"lat": 13.7, "lon": 101.0},
        opacity=0.75,
        labels={metric: metric.replace("_", " ").title()},
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=650)
    st.plotly_chart(fig, use_container_width=True)

    # Detail table below the map -- one row per province for the selected crop/year.
    st.subheader(f"Provinces growing {selected_crop} ({selected_year})")
    st.dataframe(
        filtered[["crop", "year", "province", "SHK_region", metric]]
        .sort_values(metric, ascending=False)
        .reset_index(drop=True),
        hide_index=True,
        use_container_width=True,
    )

def render_market_analysis(df, geojson):
    st.header("Market Analysis: New Chemical Targeting")
    st.caption(
        "Pick the crop(s) your new product targets to see which provinces "
        "and company sales regions (SHK_region) to prioritize."
    )

    target_crops = st.multiselect(
        "Target crop(s)", sorted(df["crop"].unique()), key="market_analysis_crops"
    )
    if not target_crops:
        st.info("Select one or more crops above to see the target analysis.")
        return

    metric = st.selectbox(
        "Metric", ["area_planted_rai", "area_harvested_rai"], key="market_analysis_metric"
    )

    # Use each crop's own latest available year -- crops don't all share the
    # same data recency (e.g. fruit crops lagging behind field crops).
    latest_year_per_crop = df[df["crop"].isin(target_crops)].groupby("crop")["year"].max()
    target_df = pd.concat(
        [df[(df["crop"] == crop) & (df["year"] == year)]
         for crop, year in latest_year_per_crop.items()],
        ignore_index=True,
    )
    st.caption(
        "Year used per crop: "
        + ", ".join(f"{c} ({y})" for c, y in latest_year_per_crop.items())
    )

    # Province-level ranking: combined target area, which of the chosen crops
    # are actually grown there.
    province_summary = (
        target_df.groupby("province", as_index=False)
        .agg(
            total_area=(metric, "sum"),
            crops_present=("crop", lambda s: ", ".join(sorted(s.unique()))),
            SHK_region=("SHK_region", "first"),
        )
        .sort_values("total_area", ascending=False)
        .reset_index(drop=True)
    )

    # SHK_region-level ranking: which company sales region to emphasize.
    shk_summary = (
        target_df.groupby("SHK_region", as_index=False)
        .agg(total_area=(metric, "sum"), province_count=("province", "nunique"))
        .sort_values("total_area", ascending=False)
        .reset_index(drop=True)
    )

    st.subheader("Combined target coverage map")
    fig = px.choropleth_map(
        province_summary,
        geojson=geojson,
        locations="province",
        featureidkey="properties.name",
        color="total_area",
        color_continuous_scale="Oranges",
        map_style="carto-positron",
        zoom=4.5,
        center={"lat": 13.7, "lon": 101.0},
        opacity=0.75,
        labels={"total_area": metric.replace("_", " ").title()},
    )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=550)
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("Target provinces (ranked)")
        st.dataframe(province_summary, hide_index=True, use_container_width=True)
    with col_b:
        st.subheader("SHK regions to emphasize")
        st.dataframe(shk_summary, hide_index=True, use_container_width=True)

def main():
    st.set_page_config(layout="wide")
    st.title("Crop Cultivation by Province")

    geojson = load_geojson()
    df = load_crop_data()

    with st.expander("Debug: province names in geojson vs your data"):
        geo_names = set(build_name_lookup(geojson))
        data_names = set(df["province"].unique())
        st.write("In your data but NOT in geojson (fix spelling):", data_names - geo_names)

    render_crop_explorer(df, geojson)
    st.divider()
    render_market_analysis(df, geojson)

if __name__ == "__main__":
    main()
